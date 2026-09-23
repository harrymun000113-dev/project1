"""아주 단순한 인메모리 비동기 작업 러너.

첫 조회 시 Comtrade·SerpAPI·환율·관세 호출이 겹치면 수십 초가 걸릴 수 있어(§5.4.5),
`/api/analyze`가 즉시 202 + job_id를 돌려주고 프론트가 `/api/jobs/<id>`를 폴링하게 한다
(§6.5, §7.2). 별도 큐/워커 없이 스레드 하나로 처리하는 v1 수준의 구현이다.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable

log = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_pending_by_key: dict[str, str] = {}  # 같은 key(예: hs6)로 이미 뜬 pending job이 있으면 재사용
_lock = threading.Lock()
_JOB_TTL = 3600  # 완료된 작업 결과를 메모리에 남겨두는 시간


def start(compute: Callable[[], dict], key: str | None = None) -> str:
    """`key`가 주어지고 그 key로 아직 끝나지 않은 job이 있으면, 새 스레드를 띄우지 않고
    그 job_id를 그대로 돌려준다. 같은 HS코드를 결과가 나오기 전에 다시 검색했을 때
    (§흔한 UX: "안 되는 줄 알고 또 눌렀다") 백그라운드 job이 계속 쌓여 서로 외부 API
    레이트리밋을 나눠 쓰며 전부 느려지는 문제를 막기 위함이다."""
    with _lock:
        if key is not None:
            existing = _pending_by_key.get(key)
            if existing and existing in _jobs and _jobs[existing]["status"] == "pending":
                return existing

        job_id = uuid.uuid4().hex
        _jobs[job_id] = {"status": "pending", "result": None, "error": None, "created_at": time.time()}
        if key is not None:
            _pending_by_key[key] = job_id

    def _run():
        try:
            result = compute()
            with _lock:
                _jobs[job_id].update(status="done", result=result)
        except Exception as e:  # 잡 스레드가 죽으면 폴링이 영원히 pending 상태가 되므로 반드시 흡수
            log.exception("job %s failed", job_id)
            with _lock:
                _jobs[job_id].update(status="error", error=str(e))
        finally:
            if key is not None:
                with _lock:
                    if _pending_by_key.get(key) == job_id:
                        _pending_by_key.pop(key, None)

    threading.Thread(target=_run, daemon=True, name=f"analyze-job-{job_id[:8]}").start()
    _gc()
    return job_id


def get(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _gc() -> None:
    cutoff = time.time() - _JOB_TTL
    with _lock:
        stale = [jid for jid, j in _jobs.items() if j["created_at"] < cutoff]
        for jid in stale:
            _jobs.pop(jid, None)

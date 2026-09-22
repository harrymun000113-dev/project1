"""작은 공용 헬퍼."""
from __future__ import annotations

import re


def normalize_hs(raw: str) -> tuple[str | None, bool]:
    """HS 코드 입력을 6자리로 정규화한다 (§3.1).

    - 숫자 이외 문자는 제거한다.
    - 6자리보다 길면(8·10자리 등) 앞 6자리만 쓴다.
    - 6자리보다 짧으면(4자리 등) 뒤를 0으로 채워 6자리 상당의 대표 세번으로 다룬다.
    - 숫자가 하나도 없으면 (None, False)를 반환해 호출부가 BAD_HS로 처리하게 한다.

    반환값: (정규화된 hs6 또는 None, 원래 6자리가 아니었는지 여부 — True면 프론트가
    "6자리로 분석합니다" 토스트를 띄운다).
    """
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None, False
    if len(digits) == 6:
        return digits, False
    if len(digits) > 6:
        return digits[:6], True
    return digits.ljust(6, "0"), True

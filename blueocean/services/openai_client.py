"""OpenAI Chat Completions 연동 — AI Insight(§3.4.2)와 Word 보고서(`blueocean/reports.py`)
서술 생성에 공통으로 쓰는 얇은 래퍼.

`config.DEMO_OPENAI`(키가 없거나 `BLUEOCEAN_DEMO_MODE`가 강제 데모)일 때는 항상 None을
반환해 호출부가 고정 문구/규칙 기반 결과로 안전하게 폴백하게 한다. 네트워크·파싱 실패도
예외를 던지지 않고 None으로 흡수한다 — 다른 서비스들(§6.5)과 동일한 원칙으로, AI 응답
하나가 실패했다고 분석 전체나 보고서 생성이 죽으면 안 된다.
"""
from __future__ import annotations

import json
import logging

import requests

import config

log = logging.getLogger(__name__)

_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def available() -> bool:
    return (not config.DEMO_OPENAI) and bool(config.OPENAI_API_KEY)


def chat_json(system_prompt: str, user_prompt: str, *, temperature: float = 0.4, max_tokens: int = 1200) -> dict | None:
    """시스템/유저 프롬프트로 채팅을 호출하고 JSON 객체로 파싱해 돌려준다.

    키가 없거나(`available()`이 False) 요청/응답 처리 중 무엇이든 실패하면 None —
    호출부는 반드시 None을 "AI 응답 없음"으로 처리하고 자체 폴백을 써야 한다.
    """
    if not available():
        return None

    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(_CHAT_URL, headers=headers, json=payload, timeout=config.OPENAI_TIMEOUT_SEC)
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.RequestException as e:
        log.warning("OpenAI 호출 실패: %s", e)
        return None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        log.warning("OpenAI 응답 파싱 실패: %s", e)
        return None

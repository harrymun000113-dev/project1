"""작은 공용 헬퍼."""
from __future__ import annotations

import re


def _digits_only(raw: str) -> str:
    """공백·점(.)·하이픈(-) 등 구분 문자를 포함해 숫자 이외 문자를 전부 제거한다."""
    return re.sub(r"\D", "", raw or "")


def normalize_hs(raw: str) -> tuple[str | None, bool]:
    """HS 코드 입력을 6자리로 정규화한다 (§3.1).

    - 숫자 이외 문자는 제거한다.
    - 6자리보다 길면(8·10자리 등) 앞 6자리만 쓴다.
    - 6자리보다 짧으면(4자리 등) 뒤를 0으로 채워 6자리 상당의 대표 세번으로 다룬다.
    - 숫자가 하나도 없으면 (None, False)를 반환해 호출부가 BAD_HS로 처리하게 한다.

    반환값: (정규화된 hs6 또는 None, 원래 6자리가 아니었는지 여부 — True면 프론트가
    "6자리로 분석합니다" 토스트를 띄운다).
    """
    digits = _digits_only(raw)
    if not digits:
        return None, False
    if len(digits) == 6:
        return digits, False
    if len(digits) > 6:
        return digits[:6], True
    return digits.ljust(6, "0"), True


def normalize_hs6_strict(raw: str) -> str | None:
    """뉴스 검색 등, 패딩/절단 없이 "정확히 6자리"만 유효한 HS6로 받아야 하는 곳에서 쓴다.

    `normalize_hs`와 같은 구분 문자 제거 로직(`_digits_only`)을 재사용하되, 4자리를
    0으로 채우거나 8자리를 잘라내는 관대한 보정은 하지 않는다 — 이 두 보정은 "대표
    세번"으로 다루기로 한 분석(§3.1) 용도이지, 산업군·품목 매핑처럼 정확한 6자리
    코드가 필요한 조회에는 부적절하다(예: "12"를 "120000"으로 다루면 엉뚱한 품목이 됨).
    """
    digits = _digits_only(raw)
    return digits if len(digits) == 6 else None


def hs_chapter(hs6: str) -> str:
    """HS6의 앞 2자리(Chapter)."""
    return hs6[:2]

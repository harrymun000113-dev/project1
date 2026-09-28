"""Source-linked entry news candidates, never invented corporate case studies."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

import requests

import config
from .cache import disk_json_cache
from .hs_meta import product_for_hs6
from .news import _clean_text


class PrecedentSearchError(RuntimeError):
    pass


def _terms(product):
    values = [product.get("ko"), product.get("en"), *product.get("synonyms_en", [])]
    terms = []
    for value in values:
        if not value:
            continue
        terms.extend(re.split(r"[(),·/]+", value))
    terms = [re.sub(r"^(기타\s+|incl\.\s*)|\s*포함$", "", t.strip(), flags=re.I).strip() for t in terms]
    terms = [t[:-1] if t.endswith("류") else t for t in terms]
    return list(dict.fromkeys(t for t in terms if len(t) > 1 and t.lower() not in ("other", "incl.")))[:8]


def _group(terms):
    return "(" + " OR ".join('"' + t.replace('"', '') + '"' for t in terms) + ")"


@disk_json_cache(config.CACHE_DIR / "precedents", config.TTL_NEWS)
def search(hs6: str, iso3: str, country_ko: str, country_en: str, schema: int = 1) -> dict:
    product = product_for_hs6(hs6)
    terms = _terms(product)
    countries = [name for name in (country_ko, country_en) if name]
    base = {"hs_code": hs6, "iso3": iso3, "items": [], "checked_at": datetime.now(timezone.utc).isoformat()}
    if not terms:
        return {**base, "status": "unmapped_product", "message": "해당 HS 코드의 구체적인 품목명이 등록되지 않아 기업 사례를 특정할 수 없습니다."}
    query = f'{_group(countries)} {_group(terms)} (한국 OR 국내 OR "Korea") (수출 OR 진출 OR 입점 OR 공급계약 OR export) when:5y'
    url = config.GOOGLE_NEWS_RSS_URL + "?" + urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    try:
        response = requests.get(url, timeout=(4, 10), headers={"User-Agent": "BlueOceanFinder/1.0"})
        response.raise_for_status()
        if len(response.content) > 2_000_000 or b"<!DOCTYPE" in response.content.upper():
            raise PrecedentSearchError("검색 응답 형식이 올바르지 않습니다.")
        root = ET.fromstring(response.content)
        if root.tag != "rss":
            raise PrecedentSearchError("RSS 검색 응답이 아닙니다.")
    except (requests.RequestException, ET.ParseError) as exc:
        raise PrecedentSearchError("진출 관련 보도 검색에 일시적으로 연결할 수 없습니다.") from exc
    items, seen = [], set()
    for item in root.findall("./channel/item"):
        title = _clean_text(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        source = _clean_text(item.findtext("source"))
        # Show only titles explicitly referring to this country, product and entry activity.
        title_lower = title.lower()
        if not all((any(t.lower() in title_lower for t in countries),
                    any(t.lower() in title_lower for t in terms),
                    any(t in title_lower for t in ("수출", "진출", "입점", "공급", "export")))):
            continue
        if not source or urlparse(link).scheme not in ("http", "https") or not urlparse(link).netloc or title in seen:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
        seen.add(title)
        items.append({"title": title, "url": link, "source": source, "published_at": published,
                      "evidence_type": "related_news", "verification": "원문에서 기업·제품·진출 형태 확인 필요"})
        if len(items) == 5:
            break
    return {**base, "status": "found" if items else "empty", "items": items,
            "message": "선택 국가·품목과 관련된 진출 보도입니다. 정확한 HS 일치 및 기업별 진출 사실은 원문을 확인하세요." if items else "최근 5년 검색에서 국가·품목·진출 활동이 제목에 함께 확인되는 보도를 찾지 못했습니다. 진출 사례가 없다는 뜻은 아닙니다."}

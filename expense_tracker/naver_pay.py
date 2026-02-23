"""네이버페이 결제내역 쿠키 기반 스크래퍼.

네이버페이 결제내역 페이지(pay.naver.com/pc/history)의 SSR 데이터를 파싱하여
결제내역을 추출합니다. Next.js의 __NEXT_DATA__에 포함된 React Query 데이터를 사용합니다.

사용법:
    1. 브라우저에서 https://pay.naver.com 로그인
    2. F12 (개발자도구) → 네트워크 탭
    3. F5 새로고침 → 첫 번째 요청 클릭
    4. Headers → Request Headers → Cookie 값 전체 복사
    5. .env 파일의 NAVER_COOKIE에 붙여넣기
"""

import json
import re
from datetime import datetime

import pandas as pd
import requests

from . import config

NAVER_PAY_HISTORY_URL = "https://pay.naver.com/pc/history"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """'key1=val1; key2=val2' 형태의 쿠키 문자열을 dict로 변환."""
    cookies = {}
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            key, val = pair.split("=", 1)
            cookies[key.strip()] = val.strip()
    return cookies


def _extract_next_data(html: str) -> dict | None:
    """HTML에서 __NEXT_DATA__ JSON을 추출."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_payment_items(next_data: dict) -> tuple[list[dict], int]:
    """__NEXT_DATA__에서 결제 항목과 전체 페이지 수를 추출.

    Returns:
        (items, total_pages) 튜플
    """
    try:
        queries = next_data["props"]["pageProps"]["dehydratedState"]["queries"]
    except (KeyError, TypeError):
        return [], 1

    for query in queries:
        query_key = query.get("queryKey", [])
        if isinstance(query_key, list) and len(query_key) > 0 and query_key[0] == "PAYMENT_LIST":
            pages = query.get("state", {}).get("data", {}).get("pages", [])
            if not pages:
                return [], 1
            page_data = pages[0]
            items = page_data.get("items", [])
            total_pages = page_data.get("totalPage", 1)
            return items, total_pages

    return [], 1


def fetch_payment_history(
    cookie_str: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    """네이버페이 결제내역을 SSR 페이지에서 스크래핑하여 가져온다.

    pay.naver.com/pc/history 페이지를 페이지별로 로드하고,
    __NEXT_DATA__에 포함된 결제 데이터를 추출합니다.
    결제일이 start_date 이전이면 조회를 중단합니다.

    Args:
        cookie_str: 브라우저에서 복사한 Cookie 헤더 문자열
        start_date: 조회 시작일
        end_date: 조회 종료일

    Returns:
        결제내역 딕셔너리 리스트
    """
    # start/end를 timestamp로 변환 (비교용, None이면 제한 없음)
    start_ts = start_date.timestamp() * 1000 if start_date else None
    end_ts = end_date.timestamp() * 1000 if end_date else None

    cookies = _parse_cookie_string(cookie_str)
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.cookies.update(cookies)

    all_items = []
    page = 1
    max_pages = 1  # 첫 페이지에서 업데이트됨

    while page <= max_pages:
        print(f"[네이버페이] 페이지 {page} 조회 중...")

        try:
            resp = session.get(
                NAVER_PAY_HISTORY_URL,
                params={"page": page},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[네이버페이] 페이지 요청 실패: {e}")
            print("[네이버페이] 쿠키가 만료되었을 수 있습니다. 새 쿠키를 추출해주세요.")
            break

        # HTML이 아닌 경우 (리다이렉트 등)
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            print(f"[네이버페이] 예상치 못한 응답: {content_type}")
            break

        # __NEXT_DATA__ 파싱
        next_data = _extract_next_data(resp.text)
        if not next_data:
            print("[네이버페이] 페이지 데이터를 파싱할 수 없습니다. 로그인 상태를 확인해주세요.")
            break

        items, total_pages = _extract_payment_items(next_data)
        if page == 1:
            max_pages = total_pages

        if not items:
            break

        # 날짜 필터링: 최신순이므로 start_date 이전이면 중단
        reached_before_start = False
        for item in items:
            item_ts = item.get("date", 0)
            if not isinstance(item_ts, (int, float)):
                continue

            if end_ts is not None and item_ts > end_ts:
                continue  # 아직 end_date 이후 → 건너뜀
            if start_ts is not None and item_ts < start_ts:
                reached_before_start = True
                break  # start_date 이전 → 조회 중단

            all_items.append(item)

        if reached_before_start:
            break

        page += 1

    return all_items


def _normalize_item(item: dict) -> dict | None:
    """SSR 결제 항목을 통합 형식으로 변환.

    네이버페이 SSR 데이터 구조:
        _id: 결제 ID
        serviceType: CROSSBORDER / SIMPLE_PAYMENT / ...
        merchantName: 결제 처리사 (Alipay+, 나이스 등)
        product.name: 실제 가맹점/상품명
        product.price: 원화 결제금액
        date: Unix timestamp (밀리초)
        status.name: PAYMENT_COMPLETED / PAYMENT_CANCELLED / ...
        additionalData.baseCurrencyCode: 원래 통화 (JPY 등)
        additionalData.productAmountWithBaseCurrency: 외화 금액
    """
    # 결제완료 상태만 포함
    status_name = item.get("status", {}).get("name", "")
    if status_name not in ("PAYMENT_COMPLETED",):
        return None

    # 타임스탬프 → datetime
    ts = item.get("date")
    if not isinstance(ts, (int, float)):
        return None
    dt = datetime.fromtimestamp(ts / 1000)

    # 가맹점명: product.name 우선, 없으면 merchantName
    product = item.get("product", {})
    merchant = product.get("name") or item.get("merchantName", "")

    # 원화 금액
    krw_amount = product.get("price", 0) or product.get("restAmount", 0) or 0

    # 외화 정보
    additional = item.get("additionalData", {})
    currency = additional.get("baseCurrencyCode", "KRW") or "KRW"
    foreign_amount_str = additional.get("productAmountWithBaseCurrency", "")

    # 외화 금액 파싱
    if foreign_amount_str and currency != "KRW":
        try:
            amount = float(str(foreign_amount_str).replace(",", ""))
        except (ValueError, TypeError):
            amount = float(krw_amount)
    else:
        amount = float(krw_amount)
        currency = "KRW"

    return {
        "date": dt.date(),
        "time": dt.strftime("%H:%M:%S"),
        "source": "네이버페이",
        "type": f"{item.get('serviceType', '')}({status_name})",
        "merchant": str(merchant),
        "currency": currency,
        "amount": abs(amount),
        "krw_amount": abs(float(krw_amount)),
        "category": "",
    }


def parse(
    cookie_str: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """네이버페이 결제내역을 가져와 통합 DataFrame으로 반환."""
    items = fetch_payment_history(cookie_str, start_date, end_date)

    rows = []
    for item in items:
        normalized = _normalize_item(item)
        if normalized:
            rows.append(normalized)

    if not rows:
        print("[네이버페이] 조회된 결제내역이 없습니다.")
        return pd.DataFrame(columns=config.UNIFIED_COLUMNS)

    df = pd.DataFrame(rows, columns=config.UNIFIED_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["date", "time"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def parse_from_csv(
    filepath: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """수동으로 저장한 네이버페이 CSV 파일을 파싱.

    CSV 형식 (첫 줄 헤더):
        날짜,상품명,결제금액
        2026-02-13,스타벅스,4500
        2026-02-14,교보문고,15000
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")

    # 컬럼명 정규화
    col_map = {}
    for col in df.columns:
        lower = col.strip().lower()
        if "날짜" in lower or "date" in lower:
            col_map[col] = "date"
        elif "상품" in lower or "가맹점" in lower or "merchant" in lower or "name" in lower:
            col_map[col] = "merchant"
        elif "금액" in lower or "amount" in lower or "price" in lower:
            col_map[col] = "krw_amount"

    df.rename(columns=col_map, inplace=True)

    df["date"] = pd.to_datetime(df["date"])
    if start_date or end_date:
        mask = pd.Series(True, index=df.index)
        if start_date:
            mask &= df["date"] >= pd.Timestamp(start_date)
        if end_date:
            mask &= df["date"] <= pd.Timestamp(end_date)
        df = df[mask].copy()

    result = pd.DataFrame(columns=config.UNIFIED_COLUMNS)
    result["date"] = df["date"]
    result["time"] = ""
    result["source"] = "네이버페이"
    result["type"] = "결제(payment)"
    result["merchant"] = df.get("merchant", "")
    result["currency"] = "KRW"
    result["amount"] = pd.to_numeric(df["krw_amount"].astype(str).str.replace(",", ""), errors="coerce").abs()
    result["krw_amount"] = result["amount"]
    result["category"] = ""

    result.sort_values(["date", "time"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result

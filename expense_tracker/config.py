import os
from datetime import datetime

# 지원 날짜/시간 포맷 (순서대로 시도)
_DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%y-%m-%d %H:%M:%S",
    "%y/%m/%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%y-%m-%d",
    "%y/%m/%d",
]


def parse_datetime(value: str) -> datetime | None:
    """여러 포맷의 날짜/시간 문자열을 datetime으로 변환.

    지원 포맷:
        YYYY-MM-DD HH:MM:SS, YYYY/MM/DD HH:MM:SS,
        YY-MM-DD HH:MM:SS,   YY/MM/DD HH:MM:SS,
        YYYY-MM-DD, YYYY/MM/DD, YY-MM-DD, YY/MM/DD
    """
    value = value.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def get_start_date() -> datetime | None:
    """환경변수 START_DATE에서 시작 날짜/시간을 읽는다."""
    val = os.getenv("START_DATE")
    if not val:
        return None
    return parse_datetime(val)


def get_end_date() -> datetime | None:
    """환경변수 END_DATE에서 종료 날짜/시간을 읽는다."""
    val = os.getenv("END_DATE")
    if not val:
        return None
    return parse_datetime(val)

# 트래블월렛 엑셀 구조
TW_HEADER_ROW = 13  # 1-indexed (openpyxl)
TW_DATA_START_ROW = 14
TW_COLUMNS = {
    "date": "B",
    "time": "C",
    "type": "D",
    "name": "E",
    "card_number": "F",
    "currency": "G",
    "amount": "H",
    "balance": "I",
    "merchant": "J",
    "approval_number": "K",
    "exchange_rate": "L",
    "krw_amount": "M",
}

# 결제 유형 중 실제 지출로 집계할 항목
EXPENSE_TYPES = [
    "결제(payment)",
    "ATM 출금(atm withdrawal)",
    "N빵결제(split payment)",
]

# 통합 DataFrame 컬럼
UNIFIED_COLUMNS = [
    "date",
    "time",
    "source",       # "트래블월렛" or "네이버페이"
    "type",         # 결제, 충전, 환불 등
    "merchant",
    "currency",
    "amount",       # 양수 = 지출
    "krw_amount",
    "category",
]

# 카테고리 키워드 매핑 (가맹점명 기반)
# 순서 중요: 먼저 매칭되는 카테고리가 우선. 편의점을 식비보다 먼저 배치.
CATEGORY_KEYWORDS = {
    "편의점": [
        "LAWSON", "ローソン", "FAMILYMART", "ファミリーマート",
        "7-ELEVEN", "SEVEN ELEVEN", "セブンイレブン",
        "MINISTOP", "ミニストップ", "CVS",
        "씨유", "CU인천", "CU)",
    ],
    "식비": [
        # 영어
        "STARBUCKS", "MCDONALD", "MC DONALD", "KFC", "PANDA EXPRESS",
        "SUSHI", "RAMEN", "YAKINIKU", "IZAKAYA", "RESTAURANT",
        "CAFE", "COFFEE", "BAKERY", "FOOD", "DINING",
        "TORIYAKI", "SUKIYAKI", "UDON", "SOBA", "TEMPURA",
        "DONBURI", "GYUKATSU", "TONKATSU", "OKONOMIYAKI",
        "ICE CREAM", "SWEET", "MATCHA", "PALACE",
        "POKE BAR", "TIENDA BOQUERIA", "MERCATO CENTRALE",
        "MARKET", "GROCER",
        # 한국어
        "스타벅스", "맥도날드", "롯데리아",
        # 일본어 — 체인점
        "スターバックス", "マクドナルド", "吉野家", "松屋", "すき家",
        "富士そば", "丸亀製麺", "一蘭", "天下一品",
        # 일본어 — 일반 음식점/카페 키워드
        "水産", "食堂", "居酒屋", "焼肉", "焼鳥",
        "ラーメン", "そば", "うどん", "カフェ", "珈琲",
        "ベーカリー", "パン", "ビアード", "フラムドール",
        "牛かつ", "とんかつ", "カツ", "丼",
        "たまごけん",
        # 실제 가맹점 (이번 여행에서 확인)
        "REC COFFEE", "ＣＯＦＦＥＥ", "UMITO",
        "ＲＥＣ", "磯丸", "ＭＳ　ＧＡＲＤＥＮ", "MS GARDEN",
        "ＳＷＥＥＴ", "ＭＡＴＣＨＡ", "HOLIDAY ICE",
        "NENECHICKEN", "TORIKYOU", "KAWAGOEITINOYA",
    ],
    "교통": [
        "TAXI", "TRAIN", "SUBWAY", "BUS", "METRO", "RAILROAD",
        "CYCLING", "CHARICHARI", "HELLO CYCLING",
        "TRANSPORT", "SUICA", "PASMO",
        # 일본어
        "駅", "空港", "タクシー", "バス",
        "鉄道", "交通",
    ],
    "쇼핑": [
        "MATSUYA", "PARCO", "DEPARTMENT",
        "UNIQLO", "ZARA", "MUJI", "DONKI", "DON QUIJOTE",
        "AKIHABARA", "YODOBASHI", "BIC CAMERA",
        "DFS", "DUTY FREE",
        "LATTESTSPORTS", "SPORTS",
        # 일본어 — 드럭스토어/쇼핑
        "マツモトキヨシ", "ドンキ", "ドン・キホーテ",
        "ダイソー", "DAISO", "百均",
        "ユニクロ", "無印", "ヨドバシ", "ビックカメラ",
    ],
    "관광": [
        "MUSEUM", "TEMPLE", "SHRINE", "TOWER",
        "GARDEN", "PARK", "SKYTREE", "SAMUEL COCKING",
        "IWAYA", "EXPO",
        # 일본어
        "スカイツリー", "ミズマチ", "東京タワー",
        "美術館", "博物館", "神社", "寺",
        "チケット", "展望",
        # 스파/온천
        "スパ", "ラクーア", "温泉", "SPA", "ONSEN",
    ],
    "클라이밍": [
        "CLIMBING", "BOULDER", "B-PUMP", "NOBOROCK", "URBAN BASE CAMP",
        "ARRAMPICATA", "9 DEGREES",
        "クライミング", "ボルダリング",
    ],
    "숙박": [
        "HOTEL", "HOSTEL", "INN", "GUESTHOUSE", "CABIN",
        "NINE HOURS", "REMBRANDT",
        "ホテル", "旅館", "ゲストハウス",
    ],
}

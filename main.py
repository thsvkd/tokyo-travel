#!/usr/bin/env python3
"""도쿄 여행 지출 분석 프로그램.

사용법:
    # 스크립트로 실행 (환경 자동 셋업)
    ./scripts/run.sh -tw 손태형_트래블월렛_이용내역_1771602775.xlsx

    # uv로 직접 실행
    uv run tokyo-travel -tw 손태형_트래블월렛_이용내역_1771602775.xlsx
"""

from expense_tracker.cli import main

if __name__ == "__main__":
    main()

"""Click 기반 CLI 진입점."""

import os
import sys
from datetime import datetime

import click
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console

from . import analyzer, config

console = Console()

_DATE_HELP = "형식: YYYY-MM-DD [HH:MM:SS] 또는 YY-MM-DD [HH:MM:SS] (/ 구분자도 가능)"


def parse_datetime_arg(ctx, param, value: str | None) -> datetime | None:
    """CLI 날짜/시간 인자를 datetime으로 변환."""
    if value is None:
        return None
    result = config.parse_datetime(value)
    if result is None:
        raise click.BadParameter(
            f"날짜 형식이 올바르지 않습니다: {value}\n  {_DATE_HELP}"
        )
    return result


@click.command(help="도쿄 여행 지출 분석 프로그램")
@click.option(
    "--travel-wallet", "-tw",
    type=click.Path(exists=True),
    help="트래블월렛 엑셀 파일 경로",
)
@click.option(
    "--tw-password",
    type=str,
    default=None,
    help="트래블월렛 엑셀 비밀번호 (미입력 시 .env의 TW_PASSWORD 사용)",
)
@click.option(
    "--naver-pay", "-np",
    is_flag=True,
    default=False,
    help="네이버페이 결제내역 가져오기 (쿠키 필요)",
)
@click.option(
    "--naver-csv",
    type=click.Path(exists=True),
    help="네이버페이 CSV 파일 경로 (수동 저장한 경우)",
)
@click.option(
    "--start-date",
    type=str,
    default=None,
    callback=parse_datetime_arg,
    help=f"분석 시작 날짜/시간 ({_DATE_HELP})",
)
@click.option(
    "--end-date",
    type=str,
    default=None,
    callback=parse_datetime_arg,
    help=f"분석 종료 날짜/시간 ({_DATE_HELP})",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="결과 저장 경로 (.xlsx 또는 .csv)",
)
def main(
    travel_wallet: str | None,
    tw_password: str | None,
    naver_pay: bool,
    naver_csv: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    output: str | None,
) -> None:
    """도쿄 여행 지출을 분석합니다."""
    if not travel_wallet and not naver_pay and not naver_csv:
        console.print(
            "[bold red]최소 하나의 데이터 소스를 지정해주세요.[/]\n"
            "  --travel-wallet, --naver-pay, 또는 --naver-csv"
        )
        sys.exit(1)

    load_dotenv()

    # 우선순위: CLI 인자 > .env (미지정 시 None → 필터링 없음)
    s_date = start_date or config.get_start_date()
    e_date = end_date or config.get_end_date()

    if s_date or e_date:
        parts = []
        if s_date:
            parts.append(f"시작: {s_date.strftime('%Y-%m-%d %H:%M:%S')}")
        if e_date:
            parts.append(f"종료: {e_date.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"[dim]분석 기간 ─ {' | '.join(parts)}[/]")
    else:
        console.print("[dim]분석 기간 ─ 전체[/]")

    all_dfs: list[pd.DataFrame] = []

    # 트래블월렛
    if travel_wallet:
        console.print(f"[bold cyan]트래블월렛[/] 파일 로딩: {travel_wallet}")
        password = tw_password or os.getenv("TW_PASSWORD", "")
        try:
            from . import travel_wallet as tw_module

            tw_df = tw_module.parse(
                travel_wallet,
                password=password if password else None,
                start_date=s_date,
                end_date=e_date,
            )
            expenses = tw_df[tw_df["amount"] > 0]
            console.print(f"[bold cyan]트래블월렛[/] {len(expenses)}건의 지출 내역 로드 완료")
            all_dfs.append(tw_df)
        except Exception as e:
            console.print(f"[bold red]트래블월렛 로딩 실패:[/] {e}")

    # 네이버페이 (API)
    if naver_pay:
        cookie_str = os.getenv("NAVER_COOKIE", "")
        if not cookie_str:
            console.print("[bold red]NAVER_COOKIE가 설정되지 않았습니다.[/]")
            console.print(".env 파일에 NAVER_COOKIE를 설정하거나 --naver-csv를 사용하세요.")
        else:
            console.print("[bold green]네이버페이[/] API로 결제내역 조회 중...")
            try:
                from . import naver_pay as np_module

                np_df = np_module.parse(
                    cookie_str,
                    start_date=s_date,
                    end_date=e_date,
                )
                expenses = np_df[np_df["amount"] > 0]
                console.print(f"[bold green]네이버페이[/] {len(expenses)}건의 결제 내역 로드 완료")
                all_dfs.append(np_df)
            except Exception as e:
                console.print(f"[bold red]네이버페이 조회 실패:[/] {e}")

    # 네이버페이 (CSV)
    if naver_csv:
        console.print(f"[bold green]네이버페이[/] CSV 파일 로딩: {naver_csv}")
        try:
            from . import naver_pay as np_module

            np_df = np_module.parse_from_csv(
                naver_csv,
                start_date=s_date,
                end_date=e_date,
            )
            expenses = np_df[np_df["amount"] > 0]
            console.print(f"[bold green]네이버페이[/] {len(expenses)}건의 결제 내역 로드 완료")
            all_dfs.append(np_df)
        except Exception as e:
            console.print(f"[bold red]네이버페이 CSV 로딩 실패:[/] {e}")

    if not all_dfs:
        console.print("\n[bold red]로드된 데이터가 없습니다.[/]")
        sys.exit(1)

    # 데이터 합산
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = analyzer.categorize(combined)
    combined.sort_values(["date", "time"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    # 리포트 출력
    analyzer.print_report(combined)

    # 파일 저장
    if output:
        output_path = output
        if output_path.endswith(".csv"):
            expenses = analyzer.filter_expenses(combined)
            expenses.to_csv(output_path, index=False, encoding="utf-8-sig")
            console.print(f"\n[bold]CSV 저장 완료:[/] {output_path}")
        else:
            if not output_path.endswith(".xlsx"):
                output_path += ".xlsx"
            analyzer.export_to_excel(combined, output_path)


if __name__ == "__main__":
    main()

"""결제내역 통합 분석기 (Rich 기반 출력)."""

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config

console = Console()


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """가맹점명 기반으로 카테고리를 추정."""
    df = df.copy()

    def _match_category(merchant: str) -> str:
        merchant_upper = str(merchant).upper()
        for category, keywords in config.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw.upper() in merchant_upper:
                    return category
        return "기타"

    df["category"] = df["merchant"].apply(_match_category)
    return df


def filter_expenses(df: pd.DataFrame) -> pd.DataFrame:
    """실제 지출 항목만 필터링 (amount > 0)."""
    return df[df["amount"] > 0].copy()


def summary_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """날짜별 지출 요약."""
    expenses = filter_expenses(df)
    if expenses.empty:
        return pd.DataFrame()

    summary = (
        expenses.groupby(expenses["date"].dt.date)
        .agg(
            건수=("amount", "count"),
            외화합계=("amount", "sum"),
            원화합계=("krw_amount", "sum"),
        )
        .reset_index()
    )
    summary.rename(columns={"date": "날짜"}, inplace=True)
    return summary


def summary_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """카테고리별 지출 요약."""
    expenses = filter_expenses(df)
    if expenses.empty:
        return pd.DataFrame()

    summary = (
        expenses.groupby("category")
        .agg(
            건수=("amount", "count"),
            원화합계=("krw_amount", "sum"),
        )
        .sort_values("원화합계", ascending=False)
        .reset_index()
    )
    summary.rename(columns={"category": "카테고리"}, inplace=True)

    total = summary["원화합계"].sum()
    summary["비율"] = (summary["원화합계"] / total * 100).round(1)
    return summary


def summary_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """결제수단별 지출 요약."""
    expenses = filter_expenses(df)
    if expenses.empty:
        return pd.DataFrame()

    summary = (
        expenses.groupby("source")
        .agg(
            건수=("amount", "count"),
            원화합계=("krw_amount", "sum"),
        )
        .sort_values("원화합계", ascending=False)
        .reset_index()
    )
    summary.rename(columns={"source": "결제수단"}, inplace=True)
    return summary


def summary_by_currency(df: pd.DataFrame) -> pd.DataFrame:
    """통화별 지출 요약."""
    expenses = filter_expenses(df)
    if expenses.empty:
        return pd.DataFrame()

    summary = (
        expenses.groupby("currency")
        .agg(
            건수=("amount", "count"),
            외화합계=("amount", "sum"),
            원화합계=("krw_amount", "sum"),
        )
        .sort_values("원화합계", ascending=False)
        .reset_index()
    )
    summary.rename(columns={"currency": "통화"}, inplace=True)
    return summary


# ── Rich 테이블 헬퍼 ─────────────────────────────────────────


def _fmt_krw(value: float) -> str:
    return f"₩{value:,.0f}"


def _make_category_table(df: pd.DataFrame, title: str = "카테고리별 지출") -> Table:
    """카테고리별 지출 Rich 테이블 생성."""
    by_cat = summary_by_category(df)
    table = Table(title=title, show_lines=False, padding=(0, 1))
    table.add_column("카테고리", style="bold")
    table.add_column("건수", justify="right")
    table.add_column("원화합계", justify="right", style="green")
    table.add_column("비율", justify="right", style="dim")

    for _, row in by_cat.iterrows():
        table.add_row(
            str(row["카테고리"]),
            str(int(row["건수"])),
            _fmt_krw(row["원화합계"]),
            f"{row['비율']}%",
        )
    return table


def _make_date_table(df: pd.DataFrame, title: str = "날짜별 지출") -> Table:
    """날짜별 지출 Rich 테이블 생성."""
    by_date = summary_by_date(df)
    table = Table(title=title, show_lines=False, padding=(0, 1))
    table.add_column("날짜", style="bold")
    table.add_column("건수", justify="right")
    table.add_column("원화합계", justify="right", style="green")

    for _, row in by_date.iterrows():
        table.add_row(
            str(row["날짜"]),
            str(int(row["건수"])),
            _fmt_krw(row["원화합계"]),
        )
    return table


def _make_currency_table(df: pd.DataFrame, title: str = "통화별 지출") -> Table:
    """통화별 지출 Rich 테이블 생성."""
    by_currency = summary_by_currency(df)
    table = Table(title=title, show_lines=False, padding=(0, 1))
    table.add_column("통화", style="bold")
    table.add_column("건수", justify="right")
    table.add_column("외화합계", justify="right", style="cyan")
    table.add_column("원화합계", justify="right", style="green")

    for _, row in by_currency.iterrows():
        table.add_row(
            str(row["통화"]),
            str(int(row["건수"])),
            f"{row['외화합계']:,.0f}",
            _fmt_krw(row["원화합계"]),
        )
    return table


def _make_source_table(df: pd.DataFrame, title: str = "결제수단별 지출") -> Table:
    """결제수단별 지출 Rich 테이블 생성."""
    by_source = summary_by_source(df)
    table = Table(title=title, show_lines=False, padding=(0, 1))
    table.add_column("결제수단", style="bold")
    table.add_column("건수", justify="right")
    table.add_column("원화합계", justify="right", style="green")

    total_krw = by_source["원화합계"].sum()
    for _, row in by_source.iterrows():
        pct = row["원화합계"] / total_krw * 100 if total_krw else 0
        table.add_row(
            str(row["결제수단"]),
            str(int(row["건수"])),
            f"{_fmt_krw(row['원화합계'])} ({pct:.1f}%)",
        )
    return table


# ── 지불 방법별 개별 통계 ────────────────────────────────────


def _print_source_section(df: pd.DataFrame, source_name: str, color: str) -> None:
    """특정 결제수단의 개별 통계를 출력."""
    source_df = df[df["source"] == source_name]
    expenses = filter_expenses(source_df)

    if expenses.empty:
        return

    total_krw = expenses["krw_amount"].sum()
    total_count = len(expenses)

    header = Text()
    header.append(f"  {source_name}", style=f"bold {color}")
    header.append(f"  ─  총 {total_count}건  ", style="dim")
    header.append(_fmt_krw(total_krw), style=f"bold {color}")

    console.print()
    console.print(Panel(header, border_style=color, expand=True))

    # 카테고리별
    by_cat = summary_by_category(source_df)
    if not by_cat.empty:
        table = Table(show_header=True, header_style=f"bold {color}", padding=(0, 1), expand=True)
        table.add_column("카테고리", style="bold", ratio=2)
        table.add_column("건수", justify="right", ratio=1)
        table.add_column("금액", justify="right", style="green", ratio=2)
        table.add_column("비율", justify="right", style="dim", ratio=1)

        for _, row in by_cat.iterrows():
            table.add_row(
                str(row["카테고리"]),
                str(int(row["건수"])),
                _fmt_krw(row["원화합계"]),
                f"{row['비율']}%",
            )

        # 합계 행
        table.add_section()
        table.add_row(
            "합계",
            str(total_count),
            _fmt_krw(total_krw),
            "100%",
            style=f"bold {color}",
        )
        console.print(table)

    # 날짜별
    by_date = summary_by_date(source_df)
    if not by_date.empty:
        table = Table(
            title=f"{source_name} 날짜별",
            show_header=True,
            header_style=f"bold {color}",
            padding=(0, 1),
            expand=True,
        )
        table.add_column("날짜", style="bold", ratio=2)
        table.add_column("건수", justify="right", ratio=1)
        table.add_column("금액", justify="right", style="green", ratio=2)

        for _, row in by_date.iterrows():
            table.add_row(
                str(row["날짜"]),
                str(int(row["건수"])),
                _fmt_krw(row["원화합계"]),
            )
        console.print(table)


# ── 메인 리포트 ──────────────────────────────────────────────


def print_report(df: pd.DataFrame) -> None:
    """터미널에 Rich 기반 분석 리포트를 출력."""
    expenses = filter_expenses(df)
    total_krw = expenses["krw_amount"].sum()
    total_count = len(expenses)

    # 타이틀
    title = Text()
    title.append("도쿄 여행 지출 분석 리포트", style="bold white")
    console.print()
    console.print(Panel(title, border_style="bright_blue", expand=True, subtitle=f"총 {total_count}건 | {_fmt_krw(total_krw)}"))

    # ── 지불 방법별 개별 통계 ──
    sources = expenses["source"].unique()
    source_colors = {
        "트래블월렛": "cyan",
        "네이버페이": "green",
    }

    if len(sources) > 0:
        for source in sources:
            color = source_colors.get(source, "yellow")
            _print_source_section(df, source, color)

    # ── 통합 통계 ──
    if len(sources) > 1:
        console.print()
        console.print(
            Panel(
                Text("  통합 통계", style="bold bright_magenta"),
                border_style="bright_magenta",
                expand=True,
            )
        )

        # 결제수단별
        console.print(_make_source_table(df))

        # 카테고리별 (통합)
        console.print(_make_category_table(df, title="통합 카테고리별 지출"))

        # 날짜별 (통합)
        console.print(_make_date_table(df, title="통합 날짜별 지출"))

        # 통화별
        console.print(_make_currency_table(df))

    elif len(sources) == 1:
        # 단일 소스일 때도 통화별은 표시
        by_currency = summary_by_currency(df)
        if not by_currency.empty and len(by_currency) > 1:
            console.print()
            console.print(_make_currency_table(df))

    console.print()
    console.print(
        Panel(
            Text(f"  총 지출  {_fmt_krw(total_krw)}  ({total_count}건)", style="bold white"),
            border_style="bright_blue",
            expand=True,
        )
    )
    console.print()


def export_to_excel(df: pd.DataFrame, output_path: str) -> None:
    """분석 결과를 Excel 파일로 저장 (상세 + 요약 시트)."""
    expenses = filter_expenses(df)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        detail = expenses.copy()
        detail["date"] = detail["date"].dt.strftime("%Y-%m-%d")
        detail.columns = ["날짜", "시간", "결제수단", "유형", "가맹점", "통화", "금액", "원화금액", "카테고리"]
        detail.to_excel(writer, sheet_name="상세내역", index=False)

        by_date = summary_by_date(df)
        if not by_date.empty:
            by_date.to_excel(writer, sheet_name="날짜별", index=False)

        by_cat = summary_by_category(df)
        if not by_cat.empty:
            by_cat.to_excel(writer, sheet_name="카테고리별", index=False)

        by_source = summary_by_source(df)
        if not by_source.empty:
            by_source.to_excel(writer, sheet_name="결제수단별", index=False)

        by_currency = summary_by_currency(df)
        if not by_currency.empty:
            by_currency.to_excel(writer, sheet_name="통화별", index=False)

    console.print(f"\n[bold]결과가 저장되었습니다:[/] {output_path}")

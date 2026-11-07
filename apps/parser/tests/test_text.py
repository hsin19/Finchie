from datetime import date
from decimal import Decimal

import pytest

from finchie_parser.errors import LayoutError
from finchie_parser.text import amount, clean, month_day, roc_date


def test_roc_date_converts_minguo_years() -> None:
    assert roc_date("115/09/07") == date(2026, 9, 7)


def test_month_day_uses_the_closing_year() -> None:
    assert month_day("09/04", date(2026, 9, 7)) == date(2026, 9, 4)


def test_month_day_puts_december_lines_on_a_january_statement_in_the_previous_year() -> None:
    assert month_day("12/28", date(2027, 1, 7)) == date(2026, 12, 28)


def test_month_day_puts_january_lines_on_a_december_statement_in_the_next_year() -> None:
    assert month_day("01/03", date(2026, 12, 28)) == date(2027, 1, 3)


def test_month_day_allows_lines_dated_shortly_after_closing() -> None:
    assert month_day("10/20", date(2026, 10, 1)) == date(2026, 10, 20)


def test_month_day_keeps_a_line_from_months_before_closing_in_the_past() -> None:
    assert month_day("03/15", date(2026, 11, 7)) == date(2026, 3, 15)


def test_month_day_reads_february_29_on_a_leap_year_statement() -> None:
    assert month_day("02/29", date(2028, 3, 7)) == date(2028, 2, 29)


@pytest.mark.parametrize("text", ["02/29", "02/30", "13/01"])
def test_month_day_rejects_dates_that_do_not_exist_near_the_closing_date(text: str) -> None:
    with pytest.raises(LayoutError):
        month_day(text, date(2026, 3, 7))


def test_amount_keeps_decimals_exact() -> None:
    assert amount("-6,552.97") == Decimal("-6552.97")


def test_clean_folds_full_width_text_and_spaces() -> None:
    assert clean("ＵＢｅａｒ卡  網購１０％ ") == "UBear卡 網購10%"

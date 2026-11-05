import pytest

from finchie_parser.settings import Settings


def test_pdf_passwords_come_from_nested_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARSER_PDF_PASSWORDS__TAISHIN", "abc")
    monkeypatch.setenv("PARSER_PDF_PASSWORDS__HSBC", "xyz")
    settings = Settings(_env_file=None)
    assert sorted(settings.pdf_passwords) == ["hsbc", "taishin"]
    assert sorted(settings.passwords()) == ["abc", "xyz"]


def test_passwords_are_not_printed() -> None:
    settings = Settings(_env_file=None, pdf_passwords={"taishin": "abc"})
    assert "abc" not in repr(settings)

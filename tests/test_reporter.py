from src.reporter import _is_before_year, _review_reasons


def test_is_before_year_ignores_blank_and_invalid_values():
    assert _is_before_year("", 2023) is False
    assert _is_before_year(None, 2023) is False
    assert _is_before_year("not-a-date", 2023) is False


def test_is_before_year_handles_iso_dates():
    assert _is_before_year("2022-12-31T23:59:59+09:00", 2023) is True
    assert _is_before_year("2023-01-01T00:00:00+09:00", 2023) is False
    assert _is_before_year("2022-12-31T14:59:59Z", 2023) is True


def test_review_reasons_does_not_treat_missing_modified_time_as_old():
    folder = {"fileName": "인증서", "filePath": "/인증서"}
    children = [{"fileName": "certificate.pdf", "modifiedTime": ""}]

    assert "old regulatory/certificate related files" not in _review_reasons(folder, children)

"""
tests/test_parser.py - Unit tests for parser and utilities
Run with: pytest tests/ -v
"""

import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.helpers import (
    clean_text,
    extract_case_number,
    is_pdf_url,
    normalize_url,
    parse_indonesian_date,
)
from database.models import PutusanMetadata, PutusanRecord


# ─── Helpers ─────────────────────────────────────────────────────────────────

class TestCleanText:
    def test_strips_whitespace(self):
        assert clean_text("  hello   world  ") == "hello world"

    def test_handles_none(self):
        assert clean_text(None) == ""

    def test_collapses_newlines(self):
        assert clean_text("line1\n\nline2") == "line1 line2"


class TestExtractCaseNumber:
    def test_standard_case_number(self):
        title = "Putusan 123/Pdt.G/2023/PN.Jkt.Pst tentang sengketa"
        assert extract_case_number(title) == "123/Pdt.G/2023/PN.Jkt.Pst"

    def test_no_case_number(self):
        assert extract_case_number("Random title without number") is None

    def test_pid_case_number(self):
        title = "456/Pid.B/2022/PN.Bdg"
        assert extract_case_number(title) == "456/Pid.B/2022/PN.Bdg"


class TestIsPdfUrl:
    def test_pdf_extension(self):
        assert is_pdf_url("https://example.com/doc.pdf") is True

    def test_pdf_in_query(self):
        assert is_pdf_url("https://example.com/download?type=pdf") is True

    def test_non_pdf(self):
        assert is_pdf_url("https://example.com/page.html") is False


class TestNormalizeUrl:
    def test_absolute_url_unchanged(self):
        url = "https://example.com/path"
        assert normalize_url("https://base.com", url) == url

    def test_relative_url_resolved(self):
        result = normalize_url("https://base.com/dir/", "page.html")
        assert result == "https://base.com/dir/page.html"


class TestParseIndonesianDate:
    def test_iso_format(self):
        dt = parse_indonesian_date("2024-03-15")
        assert dt == datetime(2024, 3, 15)

    def test_slash_format(self):
        dt = parse_indonesian_date("15/03/2024")
        assert dt == datetime(2024, 3, 15)

    def test_indonesian_month(self):
        dt = parse_indonesian_date("12 Januari 2024")
        assert dt == datetime(2024, 1, 12)

    def test_none_input(self):
        assert parse_indonesian_date(None) is None

    def test_empty_string(self):
        assert parse_indonesian_date("") is None


# ─── Models ───────────────────────────────────────────────────────────────────

class TestPutusanRecord:
    def test_valid_record(self):
        record = PutusanRecord(
            judul="123/Pdt.G/2023/PN.Jkt.Pst",
            url_pdf="https://example.com/doc.pdf",
        )
        assert record.judul == "123/Pdt.G/2023/PN.Jkt.Pst"

    def test_judul_cleaned(self):
        record = PutusanRecord(judul="  title with spaces  ")
        assert record.judul == "title with spaces"

    def test_empty_judul_raises(self):
        with pytest.raises(Exception):
            PutusanRecord(judul="")

    def test_csv_row_keys(self):
        record = PutusanRecord(judul="Test Case")
        row = record.to_csv_row()
        assert "judul" in row
        assert "url_pdf" in row
        assert "scraped_at" in row

    def test_metadata_defaults(self):
        record = PutusanRecord(judul="Test")
        assert record.metadata.klasifikasi is None
        assert record.metadata.extra == {}

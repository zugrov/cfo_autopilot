"""
Unit-тесты: OneCOsvCsvParser
"""
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "onec"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestOneCOsvParser:
    def test_aging_format_detected(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_aging_sample.csv"))
        assert result.format == "aging"

    def test_plain_format_detected(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_plain_sample.csv"))
        assert result.format == "plain"

    def test_aging_entries_count(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_aging_sample.csv"))
        # Альфа: 0_30 (1), Бетов: 31_60 (1), Гамма: 61_90 + 90_plus (2), Дельта: пустой
        assert len(result.entries) == 4

    def test_aging_buckets_assigned(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_aging_sample.csv"))
        buckets = {e.counterparty: e.aging_bucket for e in result.entries}
        assert buckets["ООО Альфа"] == "0_30"
        assert buckets["ИП Бетов"] == "31_60"

    def test_aging_gamma_two_buckets(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_aging_sample.csv"))
        gamma = [e for e in result.entries if e.counterparty == "ЗАО Гамма"]
        assert len(gamma) == 2
        buckets = {e.aging_bucket for e in gamma}
        assert buckets == {"61_90", "90_plus"}

    def test_plain_all_unknown(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_plain_sample.csv"))
        assert all(e.aging_bucket == "unknown" for e in result.entries)

    def test_plain_amounts(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_plain_sample.csv"))
        totals = {e.counterparty: e.amount for e in result.entries}
        assert totals["ООО Альфа"] == Decimal("150000")
        assert totals["ИП Бетов"] == Decimal("80000")

    def test_all_entries_receivable(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        for fixture in ("osv_aging_sample.csv", "osv_plain_sample.csv"):
            result = OneCOsvCsvParser().parse(_read(fixture))
            assert all(e.entry_type == "receivable" for e in result.entries)

    def test_no_errors_on_valid_input(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        for fixture in ("osv_aging_sample.csv", "osv_plain_sample.csv"):
            result = OneCOsvCsvParser().parse(_read(fixture))
            assert result.errors == []

    def test_inn_parsed(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_plain_sample.csv"))
        alfa = next(e for e in result.entries if e.counterparty == "ООО Альфа")
        assert alfa.inn == "7701234567"

    def test_zero_debit_rows_skipped(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("osv_aging_sample.csv"))
        names = [e.counterparty for e in result.entries]
        assert "ООО Дельта" not in names

    def test_empty_bytes(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(b"")
        assert result.entries == []
        assert result.format == "plain"


class TestAccount62DetailParser:
    def test_account62_format_detected(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("account62_detail_sample.csv"))
        assert result.format == "account62_detail"

    def test_account62_buckets_computed(self):
        from app.services.ingestion.onec_file_adapter import (
            OneCOsvCsvParser,
            bucket_for_age_days,
        )
        from app.services.ingestion.bank_csv_parser import _parse_date_ru

        result = OneCOsvCsvParser().parse(_read("account62_detail_sample.csv"))
        as_of = result.as_of_date
        expected = {
            "ООО Альфа": bucket_for_age_days(
                max(0, (as_of - _parse_date_ru("20.05.2026")).days)
            ),
            "ИП Бетов": bucket_for_age_days(
                max(0, (as_of - _parse_date_ru("15.04.2026")).days)
            ),
            "ЗАО Гамма": bucket_for_age_days(
                max(0, (as_of - _parse_date_ru("01.03.2026")).days)
            ),
            "ООО Дельта": bucket_for_age_days(
                max(0, (as_of - _parse_date_ru("01.11.2025")).days)
            ),
        }
        for entry in result.entries:
            assert entry.aging_bucket == expected[entry.counterparty]
            assert entry.aging_bucket != "unknown"

    def test_account62_due_date_priority(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        csv = (
            "Контрагент;Дата документа;Сумма;Срок оплаты\n"
            "ООО Тест;01.01.2020;10000;01.06.2026\n"
        ).encode("utf-8")
        result = OneCOsvCsvParser().parse(csv)
        entry = result.entries[0]
        # due_date 01.06.2026 ближе → 0_30, а не 90_plus по doc_date 2020
        assert entry.aging_bucket == "0_30"

    def test_account62_skips_totals_row(self):
        from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser
        result = OneCOsvCsvParser().parse(_read("account62_detail_sample.csv"))
        names = [e.counterparty for e in result.entries]
        assert "Итого" not in names
        assert len(result.entries) == 4

    def test_bucket_for_age_days_boundaries(self):
        from app.services.ingestion.onec_file_adapter import bucket_for_age_days
        assert bucket_for_age_days(0) == "0_30"
        assert bucket_for_age_days(30) == "0_30"
        assert bucket_for_age_days(31) == "31_60"
        assert bucket_for_age_days(60) == "31_60"
        assert bucket_for_age_days(61) == "61_90"
        assert bucket_for_age_days(90) == "61_90"
        assert bucket_for_age_days(91) == "90_plus"


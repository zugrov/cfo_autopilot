"""
Unit-тесты: BankCsvParser (Сбер, Тинькофф)
"""
import os
import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "banks"


def _load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


class TestSberCsvParser:
    def test_parses_sample_file(self):
        from app.services.ingestion.bank_csv_parser import SberCsvParser
        parser = SberCsvParser()
        raw = _load_fixture("sber_sample.csv")
        result = parser.parse(raw)

        assert len(result.rows) >= 7
        assert result.bank_name == "Сбербанк"

    def test_credit_row_direction(self):
        from app.services.ingestion.bank_csv_parser import SberCsvParser
        parser = SberCsvParser()
        raw = _load_fixture("sber_sample.csv")
        result = parser.parse(raw)

        credits = [r for r in result.rows if r.direction == "credit"]
        debits = [r for r in result.rows if r.direction == "debit"]
        assert len(credits) >= 4
        assert len(debits) >= 3

    def test_amount_parsed_correctly(self):
        from app.services.ingestion.bank_csv_parser import SberCsvParser
        parser = SberCsvParser()
        raw = _load_fixture("sber_sample.csv")
        result = parser.parse(raw)

        amounts = {r.amount for r in result.rows}
        assert Decimal("500000.00") in amounts

    def test_no_fatal_errors(self):
        from app.services.ingestion.bank_csv_parser import SberCsvParser
        parser = SberCsvParser()
        raw = _load_fixture("sber_sample.csv")
        result = parser.parse(raw)
        # Не должно быть ошибок на корректном файле
        assert len(result.errors) == 0

    def test_decimal_comma(self):
        from app.services.ingestion.bank_csv_parser import _normalize_amount
        assert _normalize_amount("1 234,56") == Decimal("1234.56")
        assert _normalize_amount("500000.00") == Decimal("500000.00")
        assert _normalize_amount("1\u00a0500,00") == Decimal("1500.00")  # nbsp

    def test_encoding_cp1251(self):
        """Файл в cp1251 должен парситься без garbage."""
        from app.services.ingestion.bank_csv_parser import SberCsvParser
        raw = _load_fixture("sber_sample.csv")
        # Перекодируем в cp1251 для теста
        text = raw.decode("utf-8")
        raw_cp1251 = text.encode("cp1251")
        parser = SberCsvParser()
        result = parser.parse(raw_cp1251)
        assert len(result.rows) >= 5


class TestTinkoffCsvParser:
    def test_parses_sample_file(self):
        from app.services.ingestion.bank_csv_parser import TinkoffCsvParser
        parser = TinkoffCsvParser()
        raw = _load_fixture("tinkoff_sample.csv")
        result = parser.parse(raw)

        assert len(result.rows) >= 4
        assert result.bank_name == "Тинькофф"

    def test_negative_amount_is_debit(self):
        from app.services.ingestion.bank_csv_parser import TinkoffCsvParser
        parser = TinkoffCsvParser()
        raw = _load_fixture("tinkoff_sample.csv")
        result = parser.parse(raw)

        debits = [r for r in result.rows if r.direction == "debit"]
        assert all(r.amount > 0 for r in debits), "Suммы всегда положительные"
        assert len(debits) >= 3

    def test_positive_amount_is_credit(self):
        from app.services.ingestion.bank_csv_parser import TinkoffCsvParser
        parser = TinkoffCsvParser()
        raw = _load_fixture("tinkoff_sample.csv")
        result = parser.parse(raw)

        credits = [r for r in result.rows if r.direction == "credit"]
        assert len(credits) >= 1


class TestDeduper:
    def test_same_inputs_same_hash(self):
        import uuid
        from app.services.ingestion.deduper import compute_dedupe_hash
        cid = uuid.uuid4()
        h1 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.00"), "debit", "ООО Ромашка", "Аренда")
        h2 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.00"), "debit", "ООО Ромашка", "Аренда")
        assert h1 == h2

    def test_different_amount_different_hash(self):
        import uuid
        from app.services.ingestion.deduper import compute_dedupe_hash
        cid = uuid.uuid4()
        h1 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.00"), "debit", "ООО Ромашка", "Аренда")
        h2 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.01"), "debit", "ООО Ромашка", "Аренда")
        assert h1 != h2

    def test_inn_absent_still_dedupes(self):
        """ИНН не участвует в хеше — дубликат определяется без ИНН."""
        import uuid
        from app.services.ingestion.deduper import compute_dedupe_hash
        cid = uuid.uuid4()
        h1 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.00"), "debit", "Аренда", None)
        h2 = compute_dedupe_hash(cid, date(2026, 5, 1), Decimal("100.00"), "debit", "Аренда", None)
        assert h1 == h2

    def test_different_company_different_hash(self):
        import uuid
        from app.services.ingestion.deduper import compute_dedupe_hash
        c1 = uuid.uuid4()
        c2 = uuid.uuid4()
        h1 = compute_dedupe_hash(c1, date(2026, 5, 1), Decimal("100.00"), "debit", "Аренда", None)
        h2 = compute_dedupe_hash(c2, date(2026, 5, 1), Decimal("100.00"), "debit", "Аренда", None)
        assert h1 != h2

    def test_hash_is_64_chars(self):
        import uuid
        from app.services.ingestion.deduper import compute_dedupe_hash
        h = compute_dedupe_hash(uuid.uuid4(), date(2026, 5, 1), Decimal("100.00"), "debit", None, None)
        assert len(h) == 64

"""
OneCFileAdapter — парсер 1С файлов выгрузки.

Sprint 3: поддержка ОСВ (оборотно-сальдовая ведомость) в CSV/XML формате.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import chardet

from app.services.ingestion.bank_csv_parser import ParsedRow, ParseResult, _detect_encoding


@dataclass
class OneCEntry:
    """Запись из 1С ОСВ."""
    counterparty: str
    amount: Decimal
    entry_type: str  # receivable | payable


class OneCOsvCsvParser:
    """
    Парсер CSV-экспорта Оборотно-Сальдовой Ведомости из 1С.
    Используется для импорта дебиторки и кредиторки (Sprint 3).
    """

    BANK_NAME = "1С ОСВ CSV"

    COUNTERPARTY_COLS = {"контрагент", "наименование контрагента"}
    DEBIT_COLS = {"дебет", "дебет начало", "сальдо дебет"}
    CREDIT_COLS = {"кредит", "кредит начало", "сальдо кредит"}

    def parse(self, raw_bytes: bytes) -> ParseResult:
        encoding = _detect_encoding(raw_bytes)
        text = raw_bytes.decode(encoding, errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        rows: list[ParsedRow] = []
        errors: list[dict] = []

        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        def _find_col(candidates: set[str]) -> str | None:
            for c in candidates:
                if c in headers:
                    return headers[c]
            return None

        counterparty_col = _find_col(self.COUNTERPARTY_COLS)
        debit_col = _find_col(self.DEBIT_COLS)
        credit_col = _find_col(self.CREDIT_COLS)

        for line_num, row in enumerate(reader, start=2):
            try:
                counterparty = row.get(counterparty_col, "").strip() if counterparty_col else None
                if not counterparty:
                    continue

                debit_raw = row.get(debit_col, "0").strip() if debit_col else "0"
                credit_raw = row.get(credit_col, "0").strip() if credit_col else "0"

                from app.services.ingestion.bank_csv_parser import _normalize_amount
                debit = _normalize_amount(debit_raw) if debit_raw else Decimal(0)
                credit = _normalize_amount(credit_raw) if credit_raw else Decimal(0)

                if debit > 0:
                    rows.append(
                        ParsedRow(
                            txn_date=date.today(),
                            amount=debit,
                            direction="debit",
                            counterparty_raw=counterparty,
                            purpose="Дебиторская задолженность (1С ОСВ)",
                            raw_line=";".join(row.values()),
                        )
                    )
                if credit > 0:
                    rows.append(
                        ParsedRow(
                            txn_date=date.today(),
                            amount=credit,
                            direction="credit",
                            counterparty_raw=counterparty,
                            purpose="Кредиторская задолженность (1С ОСВ)",
                            raw_line=";".join(row.values()),
                        )
                    )
            except Exception as exc:
                errors.append({"line": line_num, "error": str(exc), "raw": ""})

        return ParseResult(
            rows=rows,
            errors=errors,
            bank_name=self.BANK_NAME,
            detected_encoding=encoding,
        )

"""
Парсер банковских CSV выписок.

Поддерживаемые банки (Sprint 1):
- Сбербанк
- Тинькофф (Т-Банк)

Sprint 2+:
- ClientBankExchange (1C формат)
- ВТБ, Альфа-Банк
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterator

import chardet


@dataclass
class ParsedRow:
    txn_date: date
    amount: Decimal
    direction: str  # credit | debit
    counterparty_raw: str | None
    purpose: str | None
    raw_line: str


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[dict]  # [{line: int, error: str, raw: str}]
    bank_name: str
    detected_encoding: str


def _detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:4096])
    encoding = result.get("encoding") or "cp1251"
    # Нормализуем windows-1251 → cp1251
    return encoding.lower().replace("windows-1251", "cp1251")


def _normalize_amount(value: str) -> Decimal:
    """Нормализует строку суммы: '1 234,56' → Decimal('1234.56')."""
    cleaned = re.sub(r"[\s\u00a0]", "", value)  # убираем пробелы и nbsp
    cleaned = cleaned.replace(",", ".")
    return Decimal(cleaned)


def _parse_date_ru(value: str) -> date:
    """DD.MM.YYYY или YYYY-MM-DD."""
    value = value.strip()
    if re.match(r"\d{2}\.\d{2}\.\d{4}", value):
        d, m, y = value[:10].split(".")
        return date(int(y), int(m), int(d))
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value[:10])
    raise ValueError(f"Unknown date format: {value!r}")


class SberCsvParser:
    """
    Сбербанк CSV выписка.
    Кодировка: windows-1251. Разделитель: ;
    Дата: DD.MM.YYYY. Суммы: отдельные колонки «Приход» и «Расход».
    """

    BANK_NAME = "Сбербанк"

    # Заголовки (нечувствительны к регистру)
    DATE_COLS = {"дата операции", "дата"}
    CREDIT_COLS = {"приход", "поступление", "зачисление"}
    DEBIT_COLS = {"расход", "списание"}
    COUNTERPARTY_COLS = {"наименование контрагента", "получатель", "плательщик"}
    PURPOSE_COLS = {"назначение платежа", "основание"}

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

        date_col = _find_col(self.DATE_COLS)
        credit_col = _find_col(self.CREDIT_COLS)
        debit_col = _find_col(self.DEBIT_COLS)
        counterparty_col = _find_col(self.COUNTERPARTY_COLS)
        purpose_col = _find_col(self.PURPOSE_COLS)

        for line_num, row in enumerate(reader, start=2):
            try:
                raw_line = ";".join(row.values())
                txn_date = _parse_date_ru(row[date_col].strip())

                credit_raw = row.get(credit_col, "").strip() if credit_col else ""
                debit_raw = row.get(debit_col, "").strip() if debit_col else ""

                if credit_raw and credit_raw not in ("0", "0.00", ""):
                    amount = _normalize_amount(credit_raw)
                    direction = "credit"
                elif debit_raw and debit_raw not in ("0", "0.00", ""):
                    amount = _normalize_amount(debit_raw)
                    direction = "debit"
                else:
                    errors.append({"line": line_num, "error": "Нет суммы", "raw": raw_line})
                    continue

                counterparty = (
                    row.get(counterparty_col, "").strip() if counterparty_col else None
                )
                purpose = row.get(purpose_col, "").strip() if purpose_col else None

                rows.append(
                    ParsedRow(
                        txn_date=txn_date,
                        amount=amount,
                        direction=direction,
                        counterparty_raw=counterparty or None,
                        purpose=purpose or None,
                        raw_line=raw_line,
                    )
                )
            except Exception as exc:
                raw_line = ";".join(row.values())
                errors.append({"line": line_num, "error": str(exc), "raw": raw_line[:256]})

        return ParseResult(rows=rows, errors=errors, bank_name=self.BANK_NAME, detected_encoding=encoding)


class TinkoffCsvParser:
    """
    Тинькофф (Т-Банк) CSV выписка.
    Кодировка: UTF-8. Разделитель: ;
    Дата: DD.MM.YYYY HH:MM:SS. Суммы: одна колонка «Сумма», знак определяет направление.
    """

    BANK_NAME = "Тинькофф"

    DATE_COLS = {"дата операции", "дата"}
    AMOUNT_COLS = {"сумма операции", "сумма"}
    COUNTERPARTY_COLS = {"описание", "получатель", "наименование"}
    PURPOSE_COLS = {"категория", "назначение"}

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

        date_col = _find_col(self.DATE_COLS)
        amount_col = _find_col(self.AMOUNT_COLS)
        counterparty_col = _find_col(self.COUNTERPARTY_COLS)
        purpose_col = _find_col(self.PURPOSE_COLS)

        for line_num, row in enumerate(reader, start=2):
            try:
                raw_line = ";".join(row.values())
                txn_date = _parse_date_ru(row[date_col].strip())

                amount_raw = row.get(amount_col, "").strip() if amount_col else ""
                if not amount_raw:
                    errors.append({"line": line_num, "error": "Нет суммы", "raw": raw_line})
                    continue

                amount_decimal = _normalize_amount(amount_raw)
                if amount_decimal < 0:
                    amount = abs(amount_decimal)
                    direction = "debit"
                else:
                    amount = amount_decimal
                    direction = "credit"

                counterparty = (
                    row.get(counterparty_col, "").strip() if counterparty_col else None
                )
                purpose = row.get(purpose_col, "").strip() if purpose_col else None

                rows.append(
                    ParsedRow(
                        txn_date=txn_date,
                        amount=amount,
                        direction=direction,
                        counterparty_raw=counterparty or None,
                        purpose=purpose or None,
                        raw_line=raw_line,
                    )
                )
            except Exception as exc:
                raw_line = ";".join(row.values())
                errors.append({"line": line_num, "error": str(exc), "raw": raw_line[:256]})

        return ParseResult(rows=rows, errors=errors, bank_name=self.BANK_NAME, detected_encoding=encoding)

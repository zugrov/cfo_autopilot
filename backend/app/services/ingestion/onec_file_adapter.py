"""
OneCFileAdapter — парсер 1С файлов выгрузки.

Поддерживаемые CSV-форматы:
  - aging: колонки по корзинам (0-30, 31-60, 61-90, 90+)
  - account62_detail: детализация счёта 62 (дата документа + сумма)
  - plain: только контрагент + итоговое дебетовое сальдо
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.services.ingestion.bank_csv_parser import (
    _detect_encoding,
    _normalize_amount,
    _parse_date_ru,
)

# Aging bucket canonical names
AgingBucket = Literal["0_30", "31_60", "61_90", "90_plus", "unknown"]
FormatType = Literal["aging", "plain", "account62_detail"]

# Дефолтные вероятности и offsets (дней) по корзинам
BUCKET_DEFAULTS: dict[str, tuple[float, int, str]] = {
    "0_30":    (0.95, 15,  "open"),
    "31_60":   (0.85, 45,  "open"),
    "61_90":   (0.70, 75,  "open"),
    "90_plus": (0.40, 105, "overdue"),
    "unknown": (0.00, 0,   "open"),   # не участвует в прогнозе
}

_SKIP_COUNTERPARTY = {"итого", "всего", "total"}


def bucket_for_age_days(age_days: int) -> AgingBucket:
    """Возраст долга в днях → aging-корзина."""
    if age_days <= 30:
        return "0_30"
    if age_days <= 60:
        return "31_60"
    if age_days <= 90:
        return "61_90"
    return "90_plus"


@dataclass
class OneCOsvEntry:
    """Одна запись из ОСВ: контрагент + сумма + корзина."""
    counterparty: str
    inn: str | None
    amount: Decimal
    entry_type: Literal["receivable"] = "receivable"
    aging_bucket: AgingBucket = "unknown"


@dataclass
class OneCOsvParseResult:
    entries: list[OneCOsvEntry]
    errors: list[dict]
    format: FormatType
    as_of_date: date


# Паттерны заголовков aging-колонок (нижний регистр, stripped)
_AGING_PATTERNS: list[tuple[str, AgingBucket]] = [
    ("0-30",     "0_30"),
    ("0–30",     "0_30"),
    ("до 30",    "0_30"),
    ("до30",     "0_30"),
    ("1-30",     "0_30"),
    ("31-60",    "31_60"),
    ("31–60",    "31_60"),
    ("61-90",    "61_90"),
    ("61–90",    "61_90"),
    ("90+",      "90_plus"),
    ("свыше 90", "90_plus"),
    (">90",      "90_plus"),
    ("90 и более", "90_plus"),
]

_COUNTERPARTY_COLS = {"контрагент", "наименование контрагента", "наименование", "покупатель"}
_INN_COLS = {"инн", "инн контрагента", "иннконтрагента"}
_DEBIT_COLS = {
    "дебет", "дебет начало", "сальдо дебет",
    "сальдо дебетовое", "остаток дебет", "кон.дебет",
}
_DOC_DATE_COLS = {"дата документа", "дата", "дата операции", "дата реализации"}
_DUE_DATE_COLS = {"срок оплаты", "дата оплаты", "оплатить до"}
_AMOUNT_COLS = {"сумма", "остаток", "сальдо", "долг", "дебет"}


def _find_col(headers_lower: dict[str, str], candidates: set[str]) -> str | None:
    for c in candidates:
        if c in headers_lower:
            return headers_lower[c]
    return None


def _detect_aging_cols(headers_lower: dict[str, str]) -> dict[str, AgingBucket]:
    """Возвращает {original_header: bucket} для найденных aging-колонок."""
    result: dict[str, AgingBucket] = {}
    for h_lower, h_orig in headers_lower.items():
        for pattern, bucket in _AGING_PATTERNS:
            if pattern in h_lower:
                result[h_orig] = bucket
                break
    return result


def _compute_age_bucket(
    as_of: date,
    doc_date: date | None,
    due_date: date | None,
) -> AgingBucket:
    if due_date is not None:
        age_days = (as_of - due_date).days
    elif doc_date is not None:
        age_days = (as_of - doc_date).days
    else:
        return "unknown"
    return bucket_for_age_days(max(0, age_days))


class OneCOsvCsvParser:
    """
    Парсер CSV-экспорта из 1С (ОСВ и детализация счёта 62).
    Возвращает OneCOsvParseResult с дебиторкой.

    Формат aging: колонки по корзинам → вероятностный прогноз.
    Формат account62_detail: дата документа + сумма → aging из возраста долга.
    Формат plain: итоговое дебетовое сальдо → bucket=unknown.
    """

    def parse(self, raw_bytes: bytes) -> OneCOsvParseResult:
        encoding = _detect_encoding(raw_bytes)
        text = raw_bytes.decode(encoding, errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")

        fieldnames = reader.fieldnames or []
        headers_lower = {h.strip().lower(): h for h in fieldnames}

        counterparty_col = _find_col(headers_lower, _COUNTERPARTY_COLS)
        inn_col = _find_col(headers_lower, _INN_COLS)
        debit_col = _find_col(headers_lower, _DEBIT_COLS)
        doc_date_col = _find_col(headers_lower, _DOC_DATE_COLS)
        due_date_col = _find_col(headers_lower, _DUE_DATE_COLS)
        amount_col = _find_col(headers_lower, _AMOUNT_COLS)
        aging_cols = _detect_aging_cols(headers_lower)

        as_of = date.today()

        if aging_cols:
            fmt: FormatType = "aging"
        elif doc_date_col and amount_col:
            fmt = "account62_detail"
        elif debit_col:
            fmt = "plain"
        else:
            fmt = "plain"

        entries: list[OneCOsvEntry] = []
        errors: list[dict] = []

        for line_num, row in enumerate(reader, start=2):
            try:
                if not counterparty_col:
                    continue
                counterparty = row.get(counterparty_col, "").strip()
                if not counterparty or counterparty.lower() in _SKIP_COUNTERPARTY:
                    continue

                inn = row.get(inn_col, "").strip() if inn_col else None
                inn = inn if inn else None

                if fmt == "aging":
                    for col, bucket in aging_cols.items():
                        raw = row.get(col, "0").strip()
                        if not raw or raw == "0":
                            continue
                        amount = _normalize_amount(raw)
                        if amount > 0:
                            entries.append(
                                OneCOsvEntry(
                                    counterparty=counterparty,
                                    inn=inn,
                                    amount=amount,
                                    aging_bucket=bucket,
                                )
                            )
                elif fmt == "account62_detail":
                    amount_raw = row.get(amount_col, "0").strip() if amount_col else "0"
                    if not amount_raw or amount_raw == "0":
                        continue
                    amount = _normalize_amount(amount_raw)
                    if amount <= 0:
                        continue

                    doc_date: date | None = None
                    due_date: date | None = None
                    doc_raw = row.get(doc_date_col, "").strip() if doc_date_col else ""
                    if doc_raw:
                        doc_date = _parse_date_ru(doc_raw)
                    if due_date_col:
                        due_raw = row.get(due_date_col, "").strip()
                        if due_raw:
                            due_date = _parse_date_ru(due_raw)

                    bucket = _compute_age_bucket(as_of, doc_date, due_date)
                    entries.append(
                        OneCOsvEntry(
                            counterparty=counterparty,
                            inn=inn,
                            amount=amount,
                            aging_bucket=bucket,
                        )
                    )
                else:
                    if not debit_col:
                        continue
                    raw = row.get(debit_col, "0").strip()
                    if not raw or raw == "0":
                        continue
                    amount = _normalize_amount(raw)
                    if amount > 0:
                        entries.append(
                            OneCOsvEntry(
                                counterparty=counterparty,
                                inn=inn,
                                amount=amount,
                                aging_bucket="unknown",
                            )
                        )
            except Exception as exc:
                errors.append({"line": line_num, "error": str(exc), "raw": ""})

        return OneCOsvParseResult(
            entries=entries,
            errors=errors,
            format=fmt,
            as_of_date=as_of,
        )

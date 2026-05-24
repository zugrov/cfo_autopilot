"""
OneCFileAdapter — парсер 1С файлов выгрузки.

Sprint 3: поддержка ОСВ (оборотно-сальдовая ведомость) в CSV формате.
Два формата:
  - aging: колонки по корзинам (0-30, 31-60, 61-90, 90+)
  - plain: только контрагент + итоговое дебетовое сальдо
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

import chardet

from app.services.ingestion.bank_csv_parser import _detect_encoding, _normalize_amount

# Aging bucket canonical names
AgingBucket = Literal["0_30", "31_60", "61_90", "90_plus", "unknown"]

# Дефолтные вероятности и offsets (дней) по корзинам
BUCKET_DEFAULTS: dict[str, tuple[float, int, str]] = {
    "0_30":    (0.95, 15,  "open"),
    "31_60":   (0.85, 45,  "open"),
    "61_90":   (0.70, 75,  "open"),
    "90_plus": (0.40, 105, "overdue"),
    "unknown": (0.00, 0,   "open"),   # не участвует в прогнозе
}


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
    format: Literal["aging", "plain"]
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
    ("31-60",    "31_60"),
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


class OneCOsvCsvParser:
    """
    Парсер CSV-экспорта Оборотно-Сальдовой Ведомости из 1С.
    Возвращает OneCOsvParseResult с дебиторкой (счёт 62).

    Формат aging: строки с колонками по корзинам дней → вероятностный прогноз.
    Формат plain: итоговое дебетовое сальдо → импорт без прогноза (bucket=unknown).
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
        aging_cols = _detect_aging_cols(headers_lower)

        is_aging = bool(aging_cols)
        fmt: Literal["aging", "plain"] = "aging" if is_aging else "plain"

        entries: list[OneCOsvEntry] = []
        errors: list[dict] = []

        for line_num, row in enumerate(reader, start=2):
            try:
                if not counterparty_col:
                    continue
                counterparty = row.get(counterparty_col, "").strip()
                if not counterparty:
                    continue

                inn = row.get(inn_col, "").strip() if inn_col else None
                inn = inn if inn else None

                if is_aging:
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
            as_of_date=date.today(),
        )

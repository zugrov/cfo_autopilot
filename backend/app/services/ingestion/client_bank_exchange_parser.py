"""
ClientBankExchangeParser — парсер формата 1C ClientBankExchange.

Формат: текстовый файл с секциями [СекцияРасчСчет], [Операция].
Кодировка: windows-1251. Распространён во всех российских банках.

Документация: https://its.1c.ru/db/content/metod8dev/src/developers/stds/
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterator

import chardet

from app.services.ingestion.bank_csv_parser import ParsedRow, ParseResult, _detect_encoding


def _parse_kv_section(lines: list[str]) -> dict[str, str]:
    """Парсит секцию ключ=значение из ClientBankExchange."""
    result: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _parse_cbe_date(value: str) -> date:
    """DD.MM.YYYY"""
    value = value.strip()
    if re.match(r"\d{2}\.\d{2}\.\d{4}", value):
        d, m, y = value.split(".")
        return date(int(y), int(m), int(d))
    raise ValueError(f"Unknown date: {value!r}")


class ClientBankExchangeParser:
    """
    Парсер формата ClientBankExchange (1C/банк обмен).
    Структура файла:
      1ССчет
      [СекцияРасчСчет]
      [КонецСекции]
      [Операция]
      ДатаОперации=...
      Сумма=...
      ВидОперации=Зачисление|Списание
      Плательщик=...
      Получатель=...
      НазначениеПлатежа=...
      [КонецОперации]
    """

    BANK_NAME = "ClientBankExchange"

    def parse(self, raw_bytes: bytes) -> ParseResult:
        encoding = _detect_encoding(raw_bytes)
        text = raw_bytes.decode(encoding, errors="replace")
        lines = text.splitlines()

        rows: list[ParsedRow] = []
        errors: list[dict] = []

        i = 0
        op_num = 0
        while i < len(lines):
            line = lines[i].strip()
            if line == "[Операция]":
                op_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != "[КонецОперации]":
                    op_lines.append(lines[i].strip())
                    i += 1
                op_num += 1
                try:
                    kv = _parse_kv_section(op_lines)
                    txn_date = _parse_cbe_date(kv.get("ДатаОперации", ""))
                    amount = Decimal(kv.get("Сумма", "0").replace(",", "."))
                    op_type = kv.get("ВидОперации", "").lower()
                    direction = "credit" if "зачисление" in op_type or "поступление" in op_type else "debit"
                    counterparty = kv.get("Плательщик") or kv.get("Получатель") or None
                    purpose = kv.get("НазначениеПлатежа") or None
                    rows.append(
                        ParsedRow(
                            txn_date=txn_date,
                            amount=amount,
                            direction=direction,
                            counterparty_raw=counterparty,
                            purpose=purpose,
                            raw_line="\n".join(op_lines),
                        )
                    )
                except Exception as exc:
                    errors.append({"line": op_num, "error": str(exc), "raw": str(op_lines)[:256]})
            i += 1

        return ParseResult(
            rows=rows,
            errors=errors,
            bank_name=self.BANK_NAME,
            detected_encoding=encoding,
        )

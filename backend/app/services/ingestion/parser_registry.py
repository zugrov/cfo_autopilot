"""
ParserRegistry — реестр парсеров по банку/формату.
Позволяет добавлять новые парсеры без изменения роутера.
"""
from __future__ import annotations

from typing import Protocol

from app.services.ingestion.bank_csv_parser import (
    SberCsvParser,
    TinkoffCsvParser,
    ParseResult,
)
from app.services.ingestion.client_bank_exchange_parser import ClientBankExchangeParser
from app.services.ingestion.onec_file_adapter import OneCOsvCsvParser


class CsvParser(Protocol):
    def parse(self, raw_bytes: bytes) -> ParseResult:
        ...


_REGISTRY: dict[str, CsvParser] = {
    "sber": SberCsvParser(),
    "sberbank": SberCsvParser(),
    "tinkoff": TinkoffCsvParser(),
    "tbank": TinkoffCsvParser(),
    "client_bank_exchange": ClientBankExchangeParser(),
    "cbe": ClientBankExchangeParser(),
    "onec_osv": OneCOsvCsvParser(),
}


def get_parser(bank_key: str) -> CsvParser:
    """
    Возвращает парсер по ключу банка.
    Raises ValueError если банк не поддерживается.
    """
    key = bank_key.lower().strip()
    parser = _REGISTRY.get(key)
    if parser is None:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Банк '{bank_key}' не поддерживается. Поддерживаемые: {supported}"
        )
    return parser


def supported_banks() -> list[str]:
    return sorted(set(_REGISTRY.keys()))


def register_parser(bank_key: str, parser: CsvParser) -> None:
    """Регистрирует новый парсер (для расширения в Sprint 2)."""
    _REGISTRY[bank_key.lower().strip()] = parser

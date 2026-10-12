"""Deterministic field and money semantics for indexed business table rows.

This module performs no retrieval and no currency conversion. Unsupported or
ambiguous money is rejected instead of contributing a guessed zero to a total.
"""

from __future__ import annotations

import re
from decimal import Context, Decimal, localcontext

from src.parsers.pdf_parser import FIELD_STANDARDIZATION, FinancialPDFParser

_CURRENCIES = {
    "RMB": "CNY", "人民币": "CNY", "元": "CNY",
    "美元": "USD", "US$": "USD", "港元": "HKD", "欧元": "EUR",
}
_UNITS = {"": 1, "元": 1, "万": 10_000, "万元": 10_000, "亿": 100_000_000, "亿元": 100_000_000}
_MONEY = re.compile(
    r"^(?P<prefix>人民币|CNY|RMB|USD|HKD|EUR|US\$)?\s*"
    r"(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
    r"(?P<unit>亿元|万元|亿|万|元)?\s*"
    r"(?P<suffix>人民币|美元|港元|欧元|CNY|RMB|USD|HKD|EUR)?$",
    re.IGNORECASE,
)


def normalize_currency(value: object) -> str | None:
    """Normalize an explicit currency label, retaining missing currency as None."""
    if value is None or not str(value).strip():
        return None
    label = str(value).strip().upper()
    if label in _CURRENCIES:
        return _CURRENCIES[label]
    if re.fullmatch(r"[A-Z]{3}", label):
        return label
    raise ValueError("币种无法识别")


def normalize_row(row: dict) -> tuple[dict, dict[str, str]]:
    """Accept parser-produced Chinese headers and legacy canonical headers."""
    normalized: dict = {}
    units: dict[str, str] = {}
    for raw_key, value in row.items():
        key = FinancialPDFParser._clean_header(str(raw_key))
        unit_match = re.fullmatch(r"(.+?)[（(](亿元|万元|元)[）)]", key)
        unit = ""
        if unit_match:
            key, unit = unit_match.groups()
            key = FinancialPDFParser._clean_header(key)
        canonical = FIELD_STANDARDIZATION.get(key, key)
        if canonical in normalized and normalized[canonical] != value:
            raise ValueError(f"字段 {canonical} 存在冲突")
        normalized[canonical] = value
        if unit and canonical in {"contract_amount", "holding_value"}:
            units[canonical] = unit
    return normalized, units


def parse_money(value: object, currency: object = None, unit: str = "") -> tuple[Decimal, str | None]:
    """Read an explicit number/unit/currency without inferring an absent currency.

    The base unit is one unit of the stated currency. A Chinese 元/万元/亿元
    label declares CNY. Multipliers in both a header and a value must agree.
    Decimal precision is bounded to 38 source digits; arithmetic gets 64 digits.
    """
    match = _MONEY.fullmatch(str(value).strip()) if value is not None else None
    if not match:
        raise ValueError("金额缺失或格式不明确")
    number = match["number"].replace(",", "")
    if sum(character.isdigit() for character in number) > 38:
        raise ValueError("金额超过支持的 38 位数字精度")
    value_unit = match["unit"] or ""
    if unit not in _UNITS or (unit and value_unit and _UNITS[unit] != _UNITS[value_unit]):
        raise ValueError("表头与金额单位不一致")
    currency_labels = [currency, match["prefix"], match["suffix"]]
    if "元" in (unit + value_unit):
        currency_labels.append("CNY")
    currencies = {normalized for label in currency_labels if (normalized := normalize_currency(label))}
    if len(currencies) > 1:
        raise ValueError("金额与币种声明冲突")
    with localcontext(Context(prec=64)):
        amount = Decimal(number) * _UNITS[value_unit or unit]
    return amount, next(iter(currencies), None)


def decimal_text(value: Decimal) -> str:
    """JSON-safe exact decimal; no binary floating-point conversion."""
    return format(value, "f")

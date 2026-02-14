from __future__ import annotations

import re


_DIGITS_RE = re.compile(r"\D+")


def only_digits(value: str) -> str:
    """Retorna apenas dígitos de uma string (remove pontuações e espaços)."""
    return _DIGITS_RE.sub("", (value or ""))


def format_cnpj(value: str) -> str:
    """Normaliza e formata CNPJ (14 dígitos) para 00.000.000/0000-00.

    Se o valor estiver vazio, retorna "". Se não tiver 14 dígitos, retorna o texto
    original (strip) para a UI poder validar/alertar.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    d = only_digits(raw)
    if len(d) != 14:
        return raw
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def sanitize_ie(value: str) -> str:
    """IE: mantém somente números (sem pontuações)."""
    return only_digits((value or "").strip())

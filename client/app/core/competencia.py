from __future__ import annotations

from typing import Optional
import re


def fmt_comp(yyyymm: Optional[str]) -> str:
    """'202602' -> '02/2026'"""
    if not yyyymm:
        return ""
    s = str(yyyymm).strip()
    if len(s) == 6 and s.isdigit():
        yyyy = s[:4]
        mm = s[4:]
        return f"{mm}/{yyyy}"
    return s


def label_from_comp(value: Optional[str]) -> str:
    """Converte competência do formato interno (YYYYMM) para rótulo (MM/AAAA).

    Se já vier no formato "MM/AAAA" (ou qualquer outro), retorna como está.
    """
    return fmt_comp(value)


def parse_comp_label(label: str) -> Optional[str]:
    """'02/2026' -> '202602'; '(todas)' -> None"""
    if not label:
        return None
    s = str(label).strip()
    if not s:
        return None
    if s.lower() in {"(todas)", "todas", "todos"}:
        return None
    # aceita somente MM/YYYY numérico
    if re.match(r"^(0[1-9]|1[0-2])/\d{4}$", s):
        mm, yyyy = s.split("/", 1)
        return f"{yyyy}{mm}"
    return None


def format_comp_label(internal: Optional[str]) -> str:
    if not internal:
        return "Todas"
    return fmt_comp(internal)

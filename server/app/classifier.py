from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from .db import get_data_dir


def _normalize(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_competencia(raw: str) -> Optional[str]:
    if not raw:
        return None
    m = re.search(r"\b(\d{2})[-/](\d{4})\b", raw)
    if not m:
        m = re.search(r"\b(\d{2})(\d{4})\b", raw)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


@dataclass(frozen=True)
class Pattern:
    name: str
    tipo: str
    grupo: str
    orgao: str
    tributo: str
    subgrupo: Optional[str]
    patterns: List[str]


PATTERNS: List[Pattern] = [
    Pattern("ISSRF", "OBR", "Obrigações", "Municipal", "ISSRF", None, [r"\bISSRF\b"]),
    Pattern("ISS", "OBR", "Obrigações", "Municipal", "ISS", None, [r"\bISS\b"]),
    Pattern("GR ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bGR\s+ICMS\b"]),
    Pattern("GA ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bGA\s+ICMS\b"]),
    Pattern("DARE ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bDARE\s+ICMS\b"]),
    Pattern("DAE ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bDAE\s+ICMS\b"]),
    Pattern("DUA ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bDUA\s+ICMS\b"]),
    Pattern("ICMS DIFAL", "OBR", "Obrigações", "Estadual", "ICMS DIFAL", "MENSAL LP/LR", [r"ICMS\s+DIFAL"]),
    Pattern("ICMS ST", "OBR", "Obrigações", "Estadual", "ICMS ST", "MENSAL LP/LR", [r"ICMS\s+ST"]),
    Pattern("ICMS A", "OBR", "Obrigações", "Estadual", "ICMS A", "MENSAL LP/LR", [r"\bICMS\s+A\b"]),
    Pattern("ICMS", "OBR", "Obrigações", "Estadual", "ICMS", "MENSAL LP/LR", [r"\bICMS\b"]),
    Pattern("DARF PIS", "OBR", "Obriga??es", "Federal", "DARF PIS", "MENSAL", [r"\bDARF\s+PIS\b"]),
    Pattern("DARF COFINS", "OBR", "Obriga??es", "Federal", "DARF COFINS", "MENSAL", [r"\bDARF\s+COFINS\b"]),
    Pattern("DARF IPI", "OBR", "Obriga??es", "Federal", "DARF IPI", "MENSAL", [r"\bDARF\s+IPI\b"]),
    Pattern("DARF CSRF", "OBR", "Obriga??es", "Federal", "DARF CSRF", "MENSAL", [r"\bDARF\s+CSRF\b"]),
    Pattern("DARF IRRF", "OBR", "Obriga??es", "Federal", "DARF IRRF", "MENSAL", [r"\bDARF\s+IRRF\b"]),
    Pattern("DARF INSS", "OBR", "Obriga??es", "Federal", "DARF INSS", "MENSAL", [r"\bDARF\s+INSS\b"]),
    Pattern("DARF IRPJ", "OBR", "Obriga??es", "Federal", "DARF IRPJ", "TRIMESTRAL", [r"\bDARF\s+IRPJ\b"]),
    Pattern("DARF CSLL", "OBR", "Obriga??es", "Federal", "DARF CSLL", "TRIMESTRAL", [r"\bDARF\s+CSLL\b"]),
    Pattern("PIS/COFINS", "OBR", "Obriga??es", "Federal", "PIS/COFINS", "MENSAL LP/LR", [r"PIS\s+E\s+COFINS"]),
    Pattern("IRPJ/CSLL", "OBR", "Obriga??es", "Federal", "IRPJ/CSLL", "TRIMESTRAL LP", [r"IRPJ\s+E\s+CSLL"]),
    Pattern("IRPJ", "OBR", "Obriga??es", "Federal", "IRPJ", "TRIMESTRAL LP", [r"\bIRPJ\b"]),
    Pattern("CSLL", "OBR", "Obriga??es", "Federal", "CSLL", "TRIMESTRAL LP", [r"\bCSLL\b"]),
    Pattern("IPI", "OBR", "Obriga??es", "Federal", "IPI", "MENSAL", [r"\bIPI\b"]),
    Pattern("CSRF", "OBR", "Obriga??es", "Federal", "CSRF", "OCASIONAL", [r"\bCSRF\b"]),
    Pattern("IRRF", "OBR", "Obriga??es", "Federal", "IRRF", "OCASIONAL", [r"\bIRRF\b"]),
    Pattern("INSS", "OBR", "Obriga??es", "Federal", "INSS", "OCASIONAL", [r"\bINSS\b"]),
    Pattern("SPED FISCAL", "ACS", "Acessórias", "Estadual", "SPED FISCAL", None, [r"SPED\s+FISCAL"]),
    Pattern("DESTDA", "ACS", "Acessórias", "Estadual", "DeSTDA", None, [r"\bDESTDA\b"]),
    Pattern("DIME", "ACS", "Acessórias", "Estadual", "DIME", None, [r"\bDIME\b"]),
    Pattern("DAPI", "ACS", "Acessórias", "Estadual", "DAPI", None, [r"\bDAPI\b"]),
    Pattern("GIA", "ACS", "Acessórias", "Estadual", "GIA", None, [r"\bGIA\b"]),
    Pattern("SPED CONTRIBUIÇÕES", "ACS", "Acessórias", "Federal", "SPED CONTRIBUIÇÕES", None, [r"SPED\s+CONTRIBUICOES"]),
    Pattern("MIT - DCTFWEB", "ACS", "Acessórias", "Federal", "MIT - DCTFWEB", None, [r"\bMIT\b", r"\bDCTFWEB\b"]),
    Pattern("REINF", "ACS", "Acessórias", "Federal", "REINF", None, [r"\bREINF\b"]),
]


def _match_pattern(text_norm: str) -> Optional[Pattern]:
    for pat in PATTERNS:
        for rx in pat.patterns:
            if re.search(rx, text_norm):
                return pat
    return None


def _infer_action(text_norm: str, tipo: Optional[str]) -> Optional[str]:
    if re.search(r"\bAPUR", text_norm):
        return "APURACAO"
    if re.search(r"\bGUIA\b|\bGR\b|\bGA\b|\bDARE\b|\bDAE\b|\bDUA\b|\bGRPR\b|\bDARF\b|\bGNRE\b|\bDAS\b", text_norm):
        return "GUIA"
    if tipo == "ACS":
        return "ENTREGA"
    return None


def _infer_subtipo(text_norm: str) -> Optional[str]:
    for key in ["GRPR", "GR", "GA", "DARE", "DAE", "DUA", "DCTFWEB", "GNRE", "DARF"]:
        if re.search(rf"\b{key}\b", text_norm):
            return key
    if re.search(r"\bDARF\s+PIS\b", text_norm):
        return "PIS"
    if re.search(r"\bDARF\s+COFINS\b", text_norm):
        return "COFINS"
    return None


def _infer_trimestre(text_norm: str) -> Optional[str]:
    m = re.search(r"\b([1-4])\s+TRIMESTRE\b", text_norm)
    if not m:
        return None
    return f"TRIMESTRE_{m.group(1)}"


def classify_filename(filename: str) -> Dict[str, Any]:
    name = Path(filename).stem
    parts = [p.strip() for p in re.split(r"\s*-\s*", name) if p.strip()]
    competencia_raw = parts[0] if len(parts) >= 2 else ""
    tarefa_raw = parts[1] if len(parts) >= 2 else (parts[0] if parts else "")
    empresa = " - ".join(parts[2:]) if len(parts) >= 3 else ""

    competencia = _parse_competencia(competencia_raw) or _parse_competencia(name)
    tarefa_norm = _normalize(tarefa_raw)
    pattern = _match_pattern(tarefa_norm)

    tipo = pattern.tipo if pattern else None
    grupo = pattern.grupo if pattern else None
    subgrupo = pattern.subgrupo if pattern else None
    orgao = pattern.orgao if pattern else None
    tributo = pattern.tributo if pattern else None
    acao = _infer_action(tarefa_norm, tipo)
    subtipo = _infer_subtipo(tarefa_norm)
    trimestre = _infer_trimestre(tarefa_norm)
    if trimestre and (subgrupo or "").startswith("TRIMESTRAL"):
        subtipo = trimestre

    confianca = 0.0
    if pattern:
        confianca = 0.9
        if acao:
            confianca = 0.95

    return {
        "filename": filename,
        "competencia": competencia,
        "empresa": empresa,
        "grupo": grupo,
        "subgrupo": subgrupo,
        "tipo": tipo,
        "orgao": orgao,
        "tributo": tributo,
        "subtipo": subtipo,
        "acao": acao,
        "confianca": confianca,
        "raw_text": tarefa_raw,
    }


def save_classification_json(data: Dict[str, Any]) -> str:
    base_dir = get_data_dir() / "classificacoes"
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = data.get("filename") or "documento"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem)[:80]
    path = base_dir / f"{stamp}_{safe}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)

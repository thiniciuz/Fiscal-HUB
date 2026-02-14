from __future__ import annotations

import os
import shutil
import sys
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from app.db.sqlite import get_attachments_dir


def resolve_pdf_path(path: str) -> Path:
    """Resolve caminho salvo (absoluto ou nome) para a pasta de anexos."""
    # Corrige casos onde o caminho veio sem a letra do drive (ex.: \Users\...)
    if path.startswith("\\") and not path.startswith("\\\\"):
        drive = os.environ.get("SystemDrive") or "C:"
        path = f"{drive}{path}"
    p = Path(path)
    attachments_dir = get_attachments_dir()
    if p.is_absolute():
        if p.exists():
            return p
        candidate = attachments_dir / p.name
        if candidate.exists():
            return candidate
        return p
    return attachments_dir / p


def store_pdf(source_path: str) -> str:
    """Copia um PDF para a pasta interna do app e devolve o nome do arquivo.

    Padrão Windows:
      %APPDATA%/notion_like_app/attachments/<uuid>.pdf

    Observação: em Linux/macOS, o app usa XDG_DATA_HOME / ~/.local/share.
    """
    src = Path(source_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError("Arquivo PDF não encontrado")

    dst_dir = get_attachments_dir()
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{uuid.uuid4().hex}.pdf"
    shutil.copy2(str(src), str(dst))
    if not dst.exists():
        raise FileNotFoundError("Falha ao copiar o PDF para a pasta de anexos.")
    # Salva apenas o nome do arquivo; o caminho base vem de get_attachments_dir()
    return dst.name


def open_with_default_app(path: str) -> None:
    """Abre um arquivo usando o visualizador padrão do sistema."""
    p = resolve_pdf_path(path)
    if not p.exists():
        # Tenta resolver em attachments quando o caminho salvo está relativo
        # ou aponta para um local antigo.
        attachments_dir = get_attachments_dir()
        candidates = []
        if not p.is_absolute():
            candidates.append(attachments_dir / p)
        candidates.append(attachments_dir / p.name)
        for c in candidates:
            if c.exists():
                p = c
                break
        else:
            raise FileNotFoundError(
                f"PDF não encontrado: {path}\n"
                f"Verifique se o arquivo está em: {attachments_dir}"
            )

    if os.name == "nt":
        os.startfile(str(p))  # type: ignore[attr-defined]
        return

    # Fallback simples (Linux/macOS) - não é o foco, mas mantém compatível.
    import subprocess

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(p)])


def safe_remove(path: Optional[str]) -> None:
    """Remove arquivo se existir (sem levantar erro)."""
    if not path:
        return
    try:
        p = resolve_pdf_path(path)
        if p.exists() and p.is_file():
            p.unlink()
    except Exception:
        pass


def write_pdf_blob_to_temp(data: bytes, filename: Optional[str] = None) -> Path:
    """Grava um PDF temporário em disco e retorna o caminho."""
    tmp_root = Path(tempfile.gettempdir()) / "41_Fiscal_HUB" / "tmp_pdf"
    tmp_root.mkdir(parents=True, exist_ok=True)
    name = (filename or "anexo.pdf").strip()
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    target = tmp_root / name
    with open(target, "wb") as f:
        f.write(data)
    return target

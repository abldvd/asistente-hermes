"""Estado persistente del asistente: JSON por nombre, con escritura atómica."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent


def estado_dir() -> Path:
    d = Path(os.environ.get("ASISTENTE_ESTADO") or RAIZ / "estado")
    d.mkdir(parents=True, exist_ok=True)
    return d


def leer_json(nombre: str, defecto: Any) -> Any:
    try:
        return json.loads((estado_dir() / f"{nombre}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def escribir_json(nombre: str, datos: Any) -> None:
    destino = estado_dir() / f"{nombre}.json"
    tmp = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, destino)


def cargar_config() -> dict:
    return json.loads((RAIZ / "config" / "asistente.json").read_text(encoding="utf-8"))

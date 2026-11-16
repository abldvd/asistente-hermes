"""Cuota de Claude: % del límite de 5 h (statusline) y contador diario de llamadas."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from asistente.estado import escribir_json, leer_json

_CONTADOR = "claude_llamadas"


@dataclass(frozen=True)
class Uso:
    pct: int | None
    fresco: bool


def leer_uso(ruta: Path, ahora: float, frescura_h: float = 5) -> Uso:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        pct, t = int(datos["pct"]), float(datos["t"])
    except (OSError, ValueError, KeyError, TypeError):
        return Uso(None, False)
    return Uso(pct, ahora - t <= frescura_h * 3600)


def puede_usar_claude(uso: Uso, explicito: bool, llamadas_hoy: int, tope: int,
                      umbral: int = 80) -> tuple[bool, str]:
    if llamadas_hoy >= tope:
        return False, f"tope diario alcanzado ({llamadas_hoy}/{tope} llamadas)"
    if not uso.fresco:
        if explicito:
            return True, "dato de uso desfasado; permitido por petición explícita"
        return False, "dato de uso desfasado; solo se permiten peticiones explícitas"
    if uso.pct is not None and uso.pct >= umbral:
        return False, f"uso del límite de 5 h al {uso.pct} % (umbral {umbral} %)"
    return True, "ok"


def llamadas_hoy(hoy: date) -> int:
    datos = leer_json(_CONTADOR, {})
    return int(datos.get("n", 0)) if datos.get("fecha") == hoy.isoformat() else 0


def registrar_llamada(hoy: date) -> int:
    n = llamadas_hoy(hoy) + 1
    escribir_json(_CONTADOR, {"fecha": hoy.isoformat(), "n": n})
    return n

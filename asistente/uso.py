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
    semana: int | None = None  # % del límite semanal


def leer_uso(ruta: Path, ahora: float, frescura_h: float = 5) -> Uso:
    try:
        datos = json.loads(Path(ruta).expanduser().read_text(encoding="utf-8"))
        pct, t = int(datos["pct"]), float(datos["t"])
        reinicio = datos.get("resets_at")
        reinicio = float(reinicio) if reinicio is not None else None
        semana = datos.get("semana")
        semana = int(semana) if semana is not None else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return Uso(None, False)
    if t > ahora + 60:  # marca en el futuro: dato no fiable
        return Uso(None, False, semana)
    if reinicio is not None and t < reinicio <= ahora:
        return Uso(0, True, semana)  # la ventana de 5 h ya se reinició después de la lectura
    return Uso(pct, ahora - t <= frescura_h * 3600, semana)


def puede_usar_claude(uso: Uso, explicito: bool, llamadas_hoy: int, tope: int,
                      umbral: int = 80, umbral_semana: int = 90) -> tuple[bool, str]:
    if llamadas_hoy >= tope:
        return False, f"tope diario alcanzado ({llamadas_hoy}/{tope} llamadas)"
    # El semanal no admite excepciones: ni petición explícita ni dato desfasado lo saltan.
    if uso.semana is not None and uso.semana >= umbral_semana:
        return False, f"límite semanal de Claude al {uso.semana} % (umbral {umbral_semana} %)"
    if not uso.fresco:
        if explicito:
            return True, "dato de uso desfasado; permitido por petición explícita"
        return False, "dato de uso desfasado; solo se permiten peticiones explícitas"
    if uso.pct is not None and uso.pct >= umbral:
        return False, f"uso del límite de 5 h al {uso.pct} % (umbral {umbral} %)"
    return True, "ok"


def llamadas_hoy(hoy: date) -> int:
    datos = leer_json(_CONTADOR, {})
    if not isinstance(datos, dict):
        return 0
    return int(datos.get("n", 0)) if datos.get("fecha") == hoy.isoformat() else 0


def registrar_llamada(hoy: date) -> int:
    n = llamadas_hoy(hoy) + 1
    escribir_json(_CONTADOR, {"fecha": hoy.isoformat(), "n": n})
    return n

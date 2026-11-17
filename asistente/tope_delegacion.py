"""Hook `pre_tool_call` de Hermes para `delegate_task`: los subagentes van a Claude (DirectSDK),
así que cada subtarea nueva pasa por el mismo tope que `claude_tope` (80 % de 5 h y tope diario).

Protocolo de shell hooks de Hermes: JSON por stdin; para bloquear se imprime
{"action": "block", "message": ...}; sin salida = permitir. Siempre sale con 0.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

from asistente.estado import cargar_config
from asistente.uso import Uso, leer_uso, llamadas_hoy, puede_usar_claude, registrar_llamada

_SIN_TAREAS_NUEVAS = {"list", "steer", "stop"}


def decidir(entrada: dict, uso: Uso, llamadas: int, tope: int, umbral: int,
            umbral_semana: int = 90) -> tuple[bool, str, int]:
    """Devuelve (bloquear, mensaje, llamadas_a_registrar)."""
    args = entrada.get("tool_input") or {}
    if not isinstance(args, dict):
        args = {}
    if args.get("action") in _SIN_TAREAS_NUEVAS:
        return False, "", 0
    tareas = args.get("tasks")
    n = len(tareas) if isinstance(tareas, list) and tareas else 1
    # Un lote de n subtareas cabe si las n caben en el tope diario.
    ok, motivo = puede_usar_claude(uso, explicito=False, llamadas_hoy=llamadas + n - 1, tope=tope,
                                   umbral=umbral, umbral_semana=umbral_semana)
    if not ok:
        if llamadas + n - 1 >= tope:
            motivo = f"tope diario alcanzado ({llamadas}/{tope} llamadas; el lote pide {n})"
        return True, (f"Subagente de Claude no disponible: {motivo}. "
                      "Haz la tarea tú mismo con el modelo local; si no hay datos privados, puedes usar la reserva "
                      "de OpenRouter (python -m asistente.openrouter, ver SOUL.md)."), 0
    return False, "", n


def _uso_actual(cfg: dict) -> Uso:
    return leer_uso(Path(cfg["ruta_uso"]), time.time(), cfg["frescura_uso_h"])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
        cfg = cargar_config()
        hoy = date.today()
        bloquear, mensaje, n = decidir(entrada, _uso_actual(cfg), llamadas_hoy(hoy),
                                       cfg["tope_claude_diario"], cfg["umbral_uso"], cfg.get("umbral_semana", 90))
    except Exception as e:  # cualquier fallo cierra la puerta
        bloquear, mensaje, n = True, f"Compuerta de delegación con error ({type(e).__name__}); no se delega.", 0
    if bloquear:
        print(json.dumps({"action": "block", "message": mensaje}, ensure_ascii=False))
        return 0
    for _ in range(n):
        registrar_llamada(hoy)
    return 0


if __name__ == "__main__":
    sys.exit(main())

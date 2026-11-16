"""Hook `pre_llm_call` de Hermes: con un juego abierto, corta el mensaje antes de cargar el modelo
local en la GPU. Si el mensaje empieza por "!", pasa igualmente.

Protocolo de shell hooks: JSON por stdin; para cortar se imprime {"action": "block", "message": ...}.
Falla abierto: si la comprobación da error, el mensaje pasa.
"""
from __future__ import annotations

import json
import sys

from asistente import juego
from asistente.estado import cargar_config

AVISO = ("Tienes un juego abierto, así que no cargo el modelo en la GPU. "
         "Si lo quieres igualmente, repite el mensaje empezando por «!».")


def decidir(entrada: dict, juego: bool) -> str | None:
    """Devuelve el mensaje de bloqueo, o None si el turno puede seguir."""
    extra = entrada.get("extra") or {}
    if extra.get("parent_session_id"):  # subagente: va a Claude, no a la GPU
        return None
    if not juego:
        return None
    if str(extra.get("user_message") or "").lstrip().startswith("!"):
        return None
    return AVISO


def _hay_juego() -> bool:
    cfg = cargar_config()
    return juego.hay_juego(juego.procesos_activos(), cfg["juegos"], juego.gpu_util(),
                           cfg["umbral_gpu"], juego.ollama_ocupado())


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
        mensaje = decidir(entrada, _hay_juego())
    except Exception:
        return 0
    if mensaje:
        print(json.dumps({"action": "block", "message": mensaje}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

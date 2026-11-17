"""Hook `post_approval_response` de Hermes: si el usuario no aprueba (rechaza, caduca, se cancela o
no llega el aviso), se anulan todos los vales pendientes."""
from __future__ import annotations

import json
import sys

from asistente import vales

_APROBADO = {"once", "session", "always"}


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
        eleccion = entrada.get("choice") or (entrada.get("extra") or {}).get("choice")
    except ValueError:
        eleccion = None
    if eleccion not in _APROBADO:
        vales.anular_todos()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Hook `post_approval_response` de Hermes: activa los vales pendientes solo si el usuario aprueba.
Si rechaza, caduca, se cancela, no llega el aviso o algo falla, se anulan todos (falla cerrado)."""
from __future__ import annotations

import json
import sys

from asistente import vales

_APROBADO = {"once", "session", "always"}


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
        eleccion = entrada.get("choice") or (entrada.get("extra") or {}).get("choice")
        if eleccion in _APROBADO:
            vales.activar_pendientes()
        else:
            vales.anular_todos()
    except Exception:
        vales.anular_todos()
    return 0


if __name__ == "__main__":
    sys.exit(main())

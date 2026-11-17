"""Hook `post_approval_response` de Hermes: si el usuario aprueba, activa SOLO el vale de la regla
aprobada (rule_key = pattern_key). Si rechaza, caduca, se cancela, no llega el aviso, no hay clave o
algo falla, se anulan todos (falla cerrado). Registra los nombres de campo recibidos (sin valores)."""
from __future__ import annotations

import json
import sys
from datetime import datetime

from asistente import vales
from asistente.estado import estado_dir

_APROBADO = {"once", "session", "always"}


def _registrar(datos: dict, eleccion, activados: int) -> None:
    try:
        with open(estado_dir() / "hook_aprobacion.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} choice={eleccion} pattern_key={datos.get('pattern_key')!r} pattern_keys={datos.get('pattern_keys')!r} "
                    f"activados={activados}" + chr(10))
    except OSError:
        pass


def main() -> int:
    datos, eleccion, activados = {}, None, 0
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
        datos = {**(entrada.get("extra") or {}), **{k: v for k, v in entrada.items() if k != "extra"}}
        eleccion = datos.get("choice")
        reglas = {str(datos.get("pattern_key") or "")} | {str(k) for k in (datos.get("pattern_keys") or [])}
        reglas |= {k.removeprefix("plugin_rule:") for k in reglas}  # Hermes antepone plugin_rule:
        reglas.discard("")
        if eleccion in _APROBADO and reglas:
            activados = vales.activar(reglas)
        else:
            vales.anular_todos()
    except Exception:
        vales.anular_todos()
    _registrar(datos, eleccion, activados)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Hook `pre_tool_call` de Hermes: la confirmación de acciones sobre correo y calendario la da una
persona, no el modelo.

- Un comando de terminal con `--confirmado` o `asistente.sugerencias confirmar N` → se escala a la
  aprobación humana de Hermes ({"action": "approve"}), mostrando el comando o el evento real. En el
  cron no hay nadie que apruebe, así que falla cerrado.
- Leer `secretos/`, tocar tokens o importar las librerías de Google o los módulos del asistente desde
  código propio → se bloquea: la única vía son las CLI, que tienen sus reglas.

Falla cerrado: si el hook no puede decidir, bloquea.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys

_BLOQUEO = re.compile(
    r"secretos[\\/]|googleapiclient|google\.oauth2|google_auth_oauthlib|google\.auth\b"
    r"|token_(seria|personal)|client_secret"
    r"|from\s+asistente(\.\w+)*\s+import|import\s+asistente",
    re.IGNORECASE)
_CONFIRMADO = re.compile(r"--confirmado\b")
_CONFIRMAR_SUG = re.compile(r"asistente\.sugerencias\s+confirmar\s+(\d+)")
_TERMINAL = {"terminal", "shell", "bash", "powershell"}


def _textos(valor) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos(v)]
    if isinstance(valor, list):
        return [t for v in valor for t in _textos(v)]
    return []


def _detalle_sugerencia(n: int) -> str:
    try:
        from datetime import datetime

        from asistente.google.gmail import ZONA
        from asistente.sugerencias import detalle
        return detalle(n, datetime.now(ZONA))
    except Exception as e:  # se aprueba igual a ciegas no: el usuario ve que no hay detalle
        return f"sugerencia {n} (no se pudo leer el detalle: {type(e).__name__})"


def _bloquear(motivo: str) -> dict:
    return {"action": "block", "message": motivo}


def decidir(entrada: dict) -> dict | None:
    herramienta = str(entrada.get("tool_name") or "")
    texto = "\n".join(_textos(entrada.get("tool_input") or {}))
    if _BLOQUEO.search(texto):
        return _bloquear("Acceso directo a credenciales o a la API de Google no permitido. "
                         "Usa las CLI del asistente (skill correo-calendario).")
    confirmado = _CONFIRMADO.search(texto)
    sug = _CONFIRMAR_SUG.search(texto)
    if not (confirmado or sug):
        return None
    if herramienta not in _TERMINAL:
        return _bloquear("Las acciones con confirmación solo se pueden lanzar como comando de terminal.")
    if sug:
        mensaje = f"¿Crear este evento en el calendario?\n{_detalle_sugerencia(int(sug.group(1)))}"
    else:
        comando = texto.strip()
        i = comando.find("-m asistente.")
        mensaje = "Acción que requiere tu aprobación:\n" + (comando[i + 3:] if i >= 0 else comando)[:600]
    clave = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]
    return {"action": "approve", "message": mensaje, "rule_key": f"confirmado:{clave}"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        r = decidir(json.loads(sys.stdin.read() or "{}"))
    except Exception as e:
        r = _bloquear(f"Hook de confirmación con error ({type(e).__name__}); acción bloqueada.")
    if r:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

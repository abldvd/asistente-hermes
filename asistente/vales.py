"""Vales de aprobación de un solo uso, firmados.

1. El hook de confirmación EMITE un vale pendiente, ligado al comando exacto, cuando pide la
   aprobación del usuario.
2. El hook post_approval_response lo ACTIVA solo si el usuario aprueba; si rechaza, caduca, se
   cancela o algo falla, se anulan todos.
3. Las CLI exigen un vale activo (además de --confirmado) para cualquier acción destructiva y lo
   CONSUMEN.

Los vales van firmados con HMAC y una clave en secretos/ (el agente no puede leerla ni escribir en
la carpeta de vales: lo bloquea el hook), así que no se pueden fabricar a mano.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shlex
import time
from pathlib import Path

from asistente.estado import estado_dir
from asistente.google.cuentas import secretos_dir

VIGENCIA_S = 120


def _dir() -> Path:
    d = estado_dir() / "vales"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clave_ruta() -> Path:
    return secretos_dir().parent / "vales.key"


def _clave() -> bytes:
    ruta = _clave_ruta()
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(secrets.token_hex(32), encoding="utf-8")
    return ruta.read_text(encoding="utf-8").strip().encode()


def _huella(modulo: str, args: list[str]) -> str:
    return hashlib.sha256(json.dumps([modulo, *args], ensure_ascii=False).encode("utf-8")).hexdigest()


def _mac(huella: str, expira: float, activo: bool) -> str:
    return hmac.new(_clave(), f"{huella}|{expira!r}|{activo}".encode(), hashlib.sha256).hexdigest()


def _escribir(ruta: Path, huella: str, expira: float, activo: bool) -> None:
    ruta.write_text(json.dumps({"expira": expira, "activo": activo, "mac": _mac(huella, expira, activo)}),
                    encoding="utf-8")


def _leer(ruta: Path) -> dict | None:
    """Vale válido (firma correcta y no caducado) o None."""
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        expira, activo, mac = float(d["expira"]), bool(d["activo"]), str(d["mac"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not hmac.compare_digest(mac, _mac(ruta.stem, expira, activo)) or time.time() > expira:
        return None
    return {"expira": expira, "activo": activo}


def emitir(modulo: str, args: list[str]) -> None:
    h = _huella(modulo, args)
    _escribir(_dir() / f"{h}.json", h, time.time() + VIGENCIA_S, False)


def activar_pendientes() -> int:
    n = 0
    for ruta in _dir().glob("*.json"):
        v = _leer(ruta)
        if v and not v["activo"]:
            _escribir(ruta, ruta.stem, v["expira"], True)
            n += 1
    return n


def consumir(modulo: str, args: list[str]) -> bool:
    ruta = _dir() / f"{_huella(modulo, args)}.json"
    v = _leer(ruta)
    try:
        ruta.unlink()
    except OSError:
        pass
    return bool(v and v["activo"])


def anular_todos() -> None:
    for f in _dir().glob("*.json"):
        try:
            f.unlink()
        except OSError:
            pass


def argv_de(comando: str) -> tuple[str, list[str]]:
    """(módulo, argumentos) de `python -m modulo args...`, como los verá sys.argv de la CLI."""
    tokens = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t
              for t in shlex.split(comando, posix=False)]
    i = tokens.index("-m")
    return tokens[i + 1], tokens[i + 2:]

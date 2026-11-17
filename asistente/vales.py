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
import os
import secrets
import shlex
import time
from pathlib import Path

from asistente.estado import estado_dir
from asistente.google.cuentas import secretos_dir

VIGENCIA_S = 360  # > approvals.timeout de Hermes (300 s)


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


def _mac(huella: str, expira: float, activo: bool, regla: str) -> str:
    return hmac.new(_clave(), f"{huella}|{expira!r}|{activo}|{regla}".encode(), hashlib.sha256).hexdigest()


def _escribir(ruta: Path, huella: str, expira: float, activo: bool, regla: str) -> None:
    ruta.write_text(json.dumps({"expira": expira, "activo": activo, "regla": regla,
                                "mac": _mac(huella, expira, activo, regla)}), encoding="utf-8")


def _leer(ruta: Path, huella: str | None = None) -> dict | None:
    """Vale válido (firma correcta y no caducado) o None."""
    huella = huella or ruta.stem
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        expira, activo, mac, regla = float(d["expira"]), bool(d["activo"]), str(d["mac"]), str(d.get("regla", ""))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not hmac.compare_digest(mac, _mac(huella, expira, activo, regla)) or time.time() > expira:
        return None
    return {"expira": expira, "activo": activo, "regla": regla}


def emitir(modulo: str, args: list[str], regla: str = "") -> None:
    """`regla` = rule_key que el hook manda a Hermes; la aprobación activa solo el vale de esa regla."""
    for ruta in _dir().glob("*.json"):  # como mucho un vale pendiente a la vez
        v = _leer(ruta)
        if not v or not v["activo"]:
            try:
                ruta.unlink()
            except OSError:
                pass
    h = _huella(modulo, args)
    _escribir(_dir() / f"{h}.json", h, time.time() + VIGENCIA_S, False, regla)


def activar(reglas: set[str]) -> int:
    """Activa solo los vales pendientes cuya regla aprobó el usuario."""
    n = 0
    for ruta in _dir().glob("*.json"):
        v = _leer(ruta)
        if v and not v["activo"] and v["regla"] and v["regla"] in reglas:
            _escribir(ruta, ruta.stem, v["expira"], True, v["regla"])
            n += 1
    return n


def activar_pendientes() -> int:
    """Solo para tests: activa todos los pendientes."""
    n = 0
    for ruta in _dir().glob("*.json"):
        v = _leer(ruta)
        if v and not v["activo"]:
            _escribir(ruta, ruta.stem, v["expira"], True, v["regla"])
            n += 1
    return n


def consumir(modulo: str, args: list[str]) -> bool:
    """Reclamar = renombrar de forma atómica: dos consumos simultáneos no pueden usar el mismo vale."""
    h = _huella(modulo, args)
    ruta = _dir() / f"{h}.json"
    reclamado = ruta.with_name(f"{h}.{secrets.token_hex(4)}.usado")
    try:
        os.replace(ruta, reclamado)
    except OSError:
        return False
    v = _leer(reclamado, h)
    try:
        reclamado.unlink()
    except OSError:
        pass
    return bool(v and v["activo"])


def anular_todos() -> None:
    for f in _dir().glob("*"):
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

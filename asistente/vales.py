"""Vales de aprobación de un solo uso.

El hook de confirmación emite un vale cuando pide la aprobación del usuario para un comando exacto.
Las CLI exigen ese vale (además de --confirmado) para cualquier acción destructiva y lo consumen.
Así, un comando camuflado que el hook no reconozca no obtiene vale y la CLI lo rechaza.
Si el usuario rechaza la aprobación (o caduca), se anulan todos los vales pendientes.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import time
from pathlib import Path

from asistente.estado import estado_dir

VIGENCIA_S = 120


def _dir() -> Path:
    d = estado_dir() / "vales"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _huella(modulo: str, args: list[str]) -> str:
    return hashlib.sha256(json.dumps([modulo, *args], ensure_ascii=False).encode("utf-8")).hexdigest()


def emitir(modulo: str, args: list[str]) -> None:
    (_dir() / f"{_huella(modulo, args)}.json").write_text(
        json.dumps({"expira": time.time() + VIGENCIA_S}), encoding="utf-8")


def consumir(modulo: str, args: list[str]) -> bool:
    ruta = _dir() / f"{_huella(modulo, args)}.json"
    try:
        expira = float(json.loads(ruta.read_text(encoding="utf-8"))["expira"])
        ruta.unlink()
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return time.time() <= expira


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

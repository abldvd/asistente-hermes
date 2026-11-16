"""Vigía de juegos: cada 30 s, si hay un juego abierto, descarga de la GPU los modelos de Ollama.

Ollama sigue abierto (sin modelos ocupa muy poca VRAM) y vuelve a cargar el modelo cuando se le pida.
Se lanza al iniciar sesión con pythonw (sin ventana); una sola instancia gracias a un puerto local.
"""
from __future__ import annotations

import json
import socket
import sys
import time
import urllib.request
from datetime import datetime
from typing import Callable

from asistente import juego
from asistente.estado import cargar_config, estado_dir

OLLAMA = "http://127.0.0.1:11434"
INTERVALO_S = 30
_PUERTO_INSTANCIA = 47811


def modelos_cargados() -> list[str]:
    with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=5) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def descargar(modelo: str) -> None:
    datos = json.dumps({"model": modelo, "keep_alive": 0}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=datos,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def paso(juego: bool, cargados: Callable[[], list[str]], descargar: Callable[[str], None]) -> int:
    """Una vuelta del bucle. Devuelve cuántos modelos se han descargado."""
    if not juego:
        return 0
    n = 0
    try:
        for m in cargados():
            descargar(m)
            n += 1
    except (OSError, ValueError):
        pass
    return n


def _juego_por_procesos_o_gpu(cfg: dict) -> bool:
    return juego.hay_juego(juego.procesos_activos(), cfg["juegos"], juego.gpu_util(),
                           cfg["umbral_gpu"], juego.ollama_ocupado())


def main() -> int:
    try:
        candado = socket.socket()
        candado.bind(("127.0.0.1", _PUERTO_INSTANCIA))
    except OSError:
        return 0  # ya hay un vigía en marcha
    registro = estado_dir() / "vigia.log"
    while True:
        try:
            n = paso(_juego_por_procesos_o_gpu(cargar_config()), modelos_cargados, descargar)
            if n:
                with open(registro, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} juego abierto: {n} modelo(s) descargado(s)\n")
        except Exception:
            pass
        time.sleep(INTERVALO_S)


if __name__ == "__main__":
    sys.exit(main())

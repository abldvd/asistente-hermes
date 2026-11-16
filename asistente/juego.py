"""¿Está el usuario jugando? Por lista de procesos o por carga de GPU ajena a Ollama."""
from __future__ import annotations

import csv
import io
import json
import subprocess
import urllib.request

_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hay_juego(procesos: list[str], juegos: list[str], gpu: int | None, umbral_gpu: int,
              ollama_activo: bool) -> bool:
    activos = {p.lower() for p in procesos}
    if any(j.lower() in activos for j in juegos):
        return True
    return gpu is not None and gpu >= umbral_gpu and not ollama_activo


def procesos_activos() -> list[str]:
    try:
        r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                           timeout=20, creationflags=_SIN_VENTANA)
    except (OSError, subprocess.SubprocessError):
        return []
    return [fila[0] for fila in csv.reader(io.StringIO(r.stdout)) if fila]


def gpu_util() -> int | None:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True,
                           timeout=20, creationflags=_SIN_VENTANA)
        return int(r.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def ollama_ocupado() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3) as resp:
            return bool(json.load(resp).get("models"))
    except (OSError, ValueError):
        return False

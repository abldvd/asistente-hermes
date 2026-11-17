"""¿Está el usuario jugando? Por lista de procesos o por carga de GPU ajena a Ollama.

Con un modelo cargado, nvidia-smi no distingue a Ollama del juego; entonces se suma el uso del
motor 3D por proceso (contadores de Windows, vía typeperf) quitando los procesos de Ollama.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import urllib.request

_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_OLLAMA = {"ollama.exe", "ollama app.exe", "llama-server.exe"}
_COLUMNA = re.compile(r"pid_(\d+)_.*engtype_3D", re.IGNORECASE)
_CONTADOR_3D = r"\GPU Engine(*engtype_3D)\Utilization Percentage"


def hay_juego(procesos: list[str], juegos: list[str], gpu: int | None, umbral_gpu: int) -> bool:
    """`gpu` = uso de GPU ajeno a Ollama (ver `gpu_para_juego`)."""
    activos = {p.lower() for p in procesos}
    if any(j.lower() in activos for j in juegos):
        return True
    return gpu is not None and gpu >= umbral_gpu


def _tasklist() -> list[list[str]]:
    try:
        r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                           timeout=8, creationflags=_SIN_VENTANA)
    except (OSError, subprocess.SubprocessError):
        return []
    return [fila for fila in csv.reader(io.StringIO(r.stdout)) if fila]


def procesos_activos() -> list[str]:
    return [fila[0] for fila in _tasklist()]


def pids_ollama() -> set[int]:
    return {int(f[1]) for f in _tasklist()
            if len(f) > 1 and f[0].lower() in _OLLAMA and f[1].isdigit()}


def gpu_ajena_de_csv(texto: str, excluidos: set[int]) -> int | None:
    """Suma el uso del motor 3D por proceso (CSV de typeperf) sin los pids excluidos; tope 100."""
    filas = list(csv.reader(io.StringIO(texto)))
    if len(filas) < 2 or len(filas[0]) != len(filas[1]):
        return None
    total, vistas = 0.0, 0
    for cabecera, valor in zip(filas[0][1:], filas[1][1:]):
        m = _COLUMNA.search(cabecera)
        if not m:
            continue
        vistas += 1
        if int(m.group(1)) in excluidos:
            continue
        try:
            total += float(valor)
        except ValueError:
            continue
    return min(100, round(total)) if vistas else None


def gpu_ajena() -> int | None:
    try:
        r = subprocess.run(["typeperf", _CONTADOR_3D, "-sc", "1"], capture_output=True, text=True,
                           timeout=8, creationflags=_SIN_VENTANA)
    except (OSError, subprocess.SubprocessError):
        return None
    return gpu_ajena_de_csv(r.stdout.strip(), pids_ollama())


def gpu_util() -> int | None:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True,
                           timeout=8, creationflags=_SIN_VENTANA)
        return int(r.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def ollama_ocupado() -> bool:
    """True si Ollama tiene algún modelo cargado en memoria (no necesariamente trabajando)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3) as resp:
            return bool(json.load(resp).get("models"))
    except (OSError, ValueError):
        return False


def gpu_para_juego() -> int | None:
    """Uso de GPU que no es de Ollama: nvidia-smi si no hay modelo cargado (rápido), si no, por proceso."""
    return gpu_ajena() if ollama_ocupado() else gpu_util()

"""Única puerta de Hermes a Claude: `claude -p` con la suscripción, con tope y herramientas acotadas.

Códigos de salida: 0 ok, 20 denegado (cuota, tope o perfil), 21 error de claude.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from asistente.estado import RAIZ, cargar_config, estado_dir
from asistente.uso import leer_uso, llamadas_hoy, puede_usar_claude, registrar_llamada

_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def cargar_perfiles() -> dict:
    return json.loads((RAIZ / "config" / "claude_perfiles.json").read_text(encoding="utf-8"))


def construir_comando(perfil: dict, prompt: str) -> list[str]:
    herramientas = perfil["allowedTools"]
    # --tools limita las herramientas cargadas (≈5K tokens de contexto en vez de ≈40K);
    # --strict-mcp-config y --setting-sources "" evitan cargar MCP, plugins y hooks del usuario.
    return ["claude", "-p", prompt,
            "--tools", herramientas, "--allowedTools", herramientas,
            "--strict-mcp-config", "--setting-sources", "",
            "--max-turns", str(perfil["max_turns"]), "--model", perfil["model"],
            "--output-format", "json"]


def ejecutar(perfil_nombre: str, prompt: str, explicito: bool,
             timeout_s: int = 600) -> tuple[int, str]:
    perfiles = cargar_perfiles()
    if perfil_nombre not in perfiles:
        return 20, f"perfil desconocido '{perfil_nombre}'; válidos: {', '.join(perfiles)}"
    cfg = cargar_config()
    hoy = date.today()
    ok, motivo = puede_usar_claude(leer_uso(Path(cfg["ruta_uso"]), time.time(), cfg["frescura_uso_h"]),
                                   explicito, llamadas_hoy(hoy), cfg["tope_claude_diario"],
                                   cfg["umbral_uso"])
    if not ok:
        return 20, f"Claude no disponible: {motivo}"

    cwd = estado_dir() / "claude_cwd"
    cwd.mkdir(exist_ok=True)
    try:
        r = subprocess.run(construir_comando(perfiles[perfil_nombre], prompt), capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout_s, cwd=cwd,
                           creationflags=_SIN_VENTANA)
    except FileNotFoundError:
        return 21, "no se encuentra el ejecutable 'claude'"
    except subprocess.TimeoutExpired:
        registrar_llamada(hoy)
        return 21, f"claude no respondió en {timeout_s} s"
    registrar_llamada(hoy)

    try:
        salida = json.loads(r.stdout)
    except ValueError:
        return 21, (r.stderr or r.stdout or "salida vacía de claude").strip()[:500]
    texto = str(salida.get("result", ""))
    if r.returncode != 0 or salida.get("is_error"):
        return 21, texto or "error de claude"
    return 0, texto


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.claude_tope")
    p.add_argument("--perfil", required=True)
    p.add_argument("--explicito", action="store_true",
                   help="el usuario lo pidió expresamente (permite dato de uso desfasado)")
    p.add_argument("--prompt-file", help="archivo con el prompt; si falta, se lee de stdin")
    a = p.parse_args(argv)
    prompt = (Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file
              else sys.stdin.read()).strip()
    if not prompt:
        print("prompt vacío")
        return 20
    codigo, texto = ejecutar(a.perfil, prompt, a.explicito)
    print(texto)
    return codigo


if __name__ == "__main__":
    sys.exit(main())

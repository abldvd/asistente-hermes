"""Reserva para cuando Claude no está disponible: una pregunta a un modelo gratis de OpenRouter.

SOLO para tareas sin datos privados (nunca correo, calendario ni archivos personales: lo prohíbe
SOUL.md). Sin herramientas: es un modelo más capaz que el local para razonar sobre el texto dado.

Códigos de salida: 0 ok, 20 denegado (sin clave o con secreto en el prompt), 21 error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from asistente.claude_tope import contiene_secreto
from asistente.estado import RAIZ, cargar_config, estado_dir

URL = "https://openrouter.ai/api/v1/chat/completions"
# Barrera en código (además de SOUL.md): nada que parezca correo sale hacia OpenRouter.
_PARECE_CORREO = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+"                                   # una dirección de correo
    r"|^\s*(from|to|cc|subject|de|para|asunto|remitente)\s*:",     # cabeceras de mensaje
    re.IGNORECASE | re.MULTILINE)
_POR_DEFECTO = ["nvidia/nemotron-3.5-super-vl:free", "baidu/ernie-5.5-flash-preview:free"]


def _clave() -> str | None:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    try:
        for linea in (RAIZ / "secretos" / ".env").read_text(encoding="utf-8").splitlines():
            k, sep, v = linea.partition("=")
            if sep and k.strip() == "OPENROUTER_API_KEY" and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def preguntar(prompt: str, modelos: list[str] | None = None, timeout_s: int = 150) -> tuple[int, str]:
    if contiene_secreto(prompt):
        return 20, "el prompt contiene el valor de un secreto (.env); no se envía a OpenRouter"
    if _PARECE_CORREO.search(prompt):
        return 20, ("el prompt parece contener datos privados (direcciones o cabeceras de correo); "
                    "no se envía a OpenRouter: hazlo con el modelo local")
    clave = _clave()
    if not clave:
        return 20, "falta OPENROUTER_API_KEY en secretos\\.env"
    if modelos is None:
        modelos = cargar_config().get("openrouter_modelos", _POR_DEFECTO)
    errores = []
    for modelo in modelos:
        cuerpo = json.dumps({"model": modelo, "messages": [
            {"role": "system", "content": "Responde en español, de forma directa."},
            {"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(URL, data=cuerpo, headers={
            "Authorization": f"Bearer {clave}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                texto = json.load(r)["choices"][0]["message"]["content"]
            if texto:
                return 0, texto
            errores.append(f"{modelo}: respuesta vacía")
        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            errores.append(f"{modelo}: {str(e).replace(clave, '***')[:200]}")
    return 21, "OpenRouter no respondió: " + "; ".join(errores)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.openrouter")
    p.add_argument("--prompt-file", required=True, help="archivo dentro de estado\\openrouter")
    a = p.parse_args(argv)
    permitido = (estado_dir() / "openrouter").resolve()
    ruta = Path(a.prompt_file).resolve()
    if permitido not in ruta.parents:
        print(f"--prompt-file debe estar dentro de {permitido}")
        return 20
    codigo, texto = preguntar(ruta.read_text(encoding="utf-8").strip())
    print(texto)
    return codigo


if __name__ == "__main__":
    sys.exit(main())

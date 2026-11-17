"""Sugerencias de eventos detectadas en el correo, pendientes de confirmación del usuario.

Estado: estado/sugerencias.json. El agente añade sugerencias desde un JSON escrito en
estado/sugerencias_in/; el usuario responde "añade N" y el agente ejecuta `confirmar N`.

CLI: python -m asistente.sugerencias {agregar --json-file F | listar | confirmar N | descartar N}
Códigos: 0 ok, 20 denegado (número inexistente, archivo fuera de su carpeta), 21 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from asistente.estado import escribir_json, estado_dir, leer_json
from asistente.google.calendario import _dt, _normalizar, a_rfc3339, crear, existe_parecido
from asistente.google.cuentas import CuentaNoAutorizada, servicio, validar_cuenta
from asistente.google.gmail import ZONA

_CLAVE = "sugerencias"


def _vigentes(ahora: datetime) -> list[dict]:
    todas = leer_json(_CLAVE, [])
    vigentes = [s for s in todas if _dt(s["inicio"]) > ahora]
    if len(vigentes) != len(todas):
        escribir_json(_CLAVE, vigentes)
    return vigentes


def _normalizada(item: dict) -> dict | None:
    try:
        cuenta = validar_cuenta(item["cuenta"])
        titulo = str(item["titulo"]).strip()
        inicio = a_rfc3339(item["inicio"])
        fin = a_rfc3339(item["fin"]) if item.get("fin") else \
            (_dt(inicio) + timedelta(hours=1)).isoformat(timespec="seconds")
    except (KeyError, ValueError, TypeError):
        return None
    if not titulo or _dt(fin) <= _dt(inicio):
        return None
    return {"cuenta": cuenta, "titulo": titulo, "inicio": inicio, "fin": fin,
            "origen_id": str(item.get("origen_id", ""))}


def agregar(items: list[dict], ahora: datetime) -> list[dict]:
    actuales = _vigentes(ahora)
    vistas = {(_normalizar(s["titulo"]), s["inicio"]) for s in actuales}
    n = max([s["n"] for s in actuales], default=0)
    nuevas = []
    for item in items:
        s = _normalizada(item) if isinstance(item, dict) else None
        if s is None or _dt(s["inicio"]) <= ahora:
            continue
        clave = (_normalizar(s["titulo"]), s["inicio"])
        if clave in vistas:
            continue
        try:
            if existe_parecido(servicio(s["cuenta"], "calendar"), s["titulo"], s["inicio"]):
                continue
        except CuentaNoAutorizada:
            pass  # se guarda igual; al confirmar se informará del problema
        n += 1
        s.update(n=n, creada=ahora.isoformat(timespec="seconds"))
        vistas.add(clave)
        nuevas.append(s)
    escribir_json(_CLAVE, actuales + nuevas)
    return nuevas


def listar(ahora: datetime) -> list[dict]:
    return _vigentes(ahora)


def _buscar(n: int, ahora: datetime) -> tuple[dict, list[dict]]:
    actuales = _vigentes(ahora)
    for s in actuales:
        if s["n"] == n:
            return s, actuales
    validas = ", ".join(str(s["n"]) for s in actuales) or "ninguna"
    raise KeyError(f"no hay sugerencia {n}; pendientes: {validas}")


def confirmar(n: int, ahora: datetime) -> dict:
    s, actuales = _buscar(n, ahora)
    ev = crear(servicio(s["cuenta"], "calendar"), s["titulo"], s["inicio"], s["fin"],
               descripcion="Sugerido a partir de un correo por el asistente.", confirmado=True)
    escribir_json(_CLAVE, [x for x in actuales if x["n"] != n])
    return {**ev, "cuenta": s["cuenta"]}


def descartar(n: int, ahora: datetime | None = None) -> None:
    s, actuales = _buscar(n, ahora or datetime.now(ZONA))
    escribir_json(_CLAVE, [x for x in actuales if x["n"] != n])


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.sugerencias")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("agregar").add_argument("--json-file", required=True)
    sub.add_parser("listar")
    for nombre in ("confirmar", "descartar"):
        sub.add_parser(nombre).add_argument("n", type=int)
    a = p.parse_args(argv)
    ahora = datetime.now(ZONA)
    try:
        if a.cmd == "agregar":
            permitido = (estado_dir() / "sugerencias_in").resolve()
            ruta = Path(a.json_file).resolve()
            if permitido not in ruta.parents:
                print(json.dumps({"error": f"--json-file debe estar dentro de {permitido}"}, ensure_ascii=False))
                return 20
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            r = agregar(datos if isinstance(datos, list) else [datos], ahora)
        elif a.cmd == "listar":
            r = listar(ahora)
        elif a.cmd == "confirmar":
            r = confirmar(a.n, ahora)
        else:
            descartar(a.n, ahora)
            r = {"descartada": a.n}
    except KeyError as e:
        print(json.dumps({"error": str(e).strip("'\"")}, ensure_ascii=False))
        return 20
    except (CuentaNoAutorizada, ValueError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 21
    except Exception as e:  # HttpError de la API
        print(json.dumps({"error": f"{type(e).__name__}: {e}"[:500]}, ensure_ascii=False))
        return 21
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Google Calendar con zona de Canarias y confirmación obligatoria para cambios.

Fechas: `YYYY-MM-DDTHH:MM` se entiende como hora local de Canarias (con su horario de verano);
también se acepta un desfase explícito (`+01:00`, `Z`). Cualquier otro formato se rechaza.

CLI: python -m asistente.google.calendario {listar,crear,mover,borrar} --cuenta C ...
Códigos: 0 ok, 20 denegado (falta --confirmado), 21 error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta

from asistente.google.cuentas import CUENTAS, CuentaNoAutorizada, servicio
from asistente.google.gmail import ZONA, Denegado

_FORMATO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?$")
_CAL = "primary"


def _dt(texto: str) -> datetime:
    texto = (texto or "").strip()
    if not _FORMATO.match(texto):
        raise ValueError(f"fecha '{texto}' no válida; usa YYYY-MM-DDTHH:MM (hora de Canarias)")
    d = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return d.replace(tzinfo=ZONA) if d.tzinfo is None else d


def a_rfc3339(texto: str) -> str:
    return _dt(texto).isoformat(timespec="seconds")


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def listar(svc, desde: str, hasta: str) -> list[dict]:
    r = svc.events().list(calendarId=_CAL, timeMin=a_rfc3339(desde), timeMax=a_rfc3339(hasta),
                          singleEvents=True, orderBy="startTime", maxResults=100).execute()
    return [{"id": e.get("id"), "titulo": e.get("summary", ""),
             "inicio": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
             "fin": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date")}
            for e in r.get("items", [])]


def existe_parecido(svc, titulo: str, inicio: str) -> bool:
    centro = _dt(inicio)
    desde = (centro - timedelta(hours=2)).isoformat(timespec="minutes")
    hasta = (centro + timedelta(hours=2)).isoformat(timespec="minutes")
    buscado = _normalizar(titulo)
    for e in listar(svc, desde, hasta):
        t = _normalizar(e["titulo"])
        if t and (t == buscado or buscado in t or t in buscado):
            return True
    return False


def _cuerpo_fechas(inicio: str, fin: str) -> dict:
    a, b = _dt(inicio), _dt(fin)
    if b <= a:
        raise ValueError("el fin debe ser posterior al inicio")
    return {"start": {"dateTime": a.isoformat(timespec="seconds"), "timeZone": "Atlantic/Canary"},
            "end": {"dateTime": b.isoformat(timespec="seconds"), "timeZone": "Atlantic/Canary"}}


def _exigir(confirmado: bool, que: str) -> None:
    if not confirmado:
        raise Denegado(f"{que} requiere confirmación del usuario (--confirmado) tras mostrarle el evento")


def crear(svc, titulo: str, inicio: str, fin: str, descripcion: str = "", confirmado: bool = False) -> dict:
    _exigir(confirmado, "crear un evento")
    body = {"summary": titulo, "description": descripcion, **_cuerpo_fechas(inicio, fin)}
    e = svc.events().insert(calendarId=_CAL, body=body).execute()
    return {"id": e.get("id"), "titulo": titulo, "inicio": body["start"]["dateTime"], "fin": body["end"]["dateTime"]}


def mover(svc, id_: str, inicio: str, fin: str, confirmado: bool = False) -> dict:
    _exigir(confirmado, "mover un evento")
    svc.events().patch(calendarId=_CAL, eventId=id_, body=_cuerpo_fechas(inicio, fin)).execute()
    return {"id": id_, "inicio": a_rfc3339(inicio), "fin": a_rfc3339(fin)}


def borrar(svc, id_: str, confirmado: bool = False) -> dict:
    _exigir(confirmado, "borrar un evento")
    svc.events().delete(calendarId=_CAL, eventId=id_).execute()
    return {"borrado": id_}


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.google.calendario", allow_abbrev=False)
    sub = p.add_subparsers(dest="cmd", required=True)
    ahora = datetime.now(ZONA)
    for nombre in ("listar", "crear", "mover", "borrar"):
        s = sub.add_parser(nombre, allow_abbrev=False)
        s.add_argument("--cuenta", required=True, choices=CUENTAS)
        if nombre == "listar":
            s.add_argument("--desde", default=ahora.isoformat(timespec="minutes"))
            s.add_argument("--hasta", default=(ahora + timedelta(days=7)).isoformat(timespec="minutes"))
            continue
        if nombre == "crear":
            s.add_argument("--titulo", required=True)
            s.add_argument("--descripcion", default="")
        else:
            s.add_argument("--id", required=True)
        if nombre in ("crear", "mover"):
            s.add_argument("--inicio", required=True)
            s.add_argument("--fin", required=True)
        s.add_argument("--confirmado", action="store_true")
    a = p.parse_args(argv)
    try:
        svc = servicio(a.cuenta, "calendar")
        if a.cmd == "listar":
            r = listar(svc, a.desde, a.hasta)
        elif a.cmd == "crear":
            r = crear(svc, a.titulo, a.inicio, a.fin, a.descripcion, a.confirmado)
        elif a.cmd == "mover":
            r = mover(svc, a.id, a.inicio, a.fin, a.confirmado)
        else:
            r = borrar(svc, a.id, a.confirmado)
    except Denegado as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
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

"""Gmail seguro: buscar, leer, etiquetar y borradores. NO existe envío ni respuesta.

Reglas de etiquetar:
- Sin --confirmado solo se pueden PONER etiquetas de la lista blanca de la cuenta
  (config/correo.json) y QUITAR UNREAD (marcar como leído).
- Todo lo demás (archivar = quitar INBOX, TRASH, SPAM, otras etiquetas) exige --confirmado,
  que el agente solo usa tras mostrar la lista y recibir la confirmación del usuario.

CLI: python -m asistente.google.gmail {buscar,leer,etiquetas,etiquetar,borrador} --cuenta C ...
Salida JSON. Códigos: 0 ok, 20 denegado (falta --confirmado), 21 error.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from asistente.google.cuentas import (CUENTAS, CuentaNoAutorizada, cargar_correo_cfg, servicio,
                                      validar_cuenta)

ZONA = ZoneInfo("Atlantic/Canary")
_SIN_CONFIRMAR_QUITAR = {"UNREAD"}


class Denegado(Exception):
    pass


def etiquetas(svc) -> dict[str, str]:
    return {e["name"]: e["id"] for e in svc.users().labels().list(userId="me").execute().get("labels", [])}


def _cabecera(msg: dict, nombre: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == nombre.lower():
            return h.get("value", "")
    return ""


def _fecha(msg: dict) -> str:
    ms = int(msg.get("internalDate", 0))
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(ZONA).isoformat()


def _resumen(msg: dict, nombres: dict[str, str]) -> dict:
    return {"id": msg["id"], "hilo": msg.get("threadId"), "fecha": _fecha(msg),
            "de": _cabecera(msg, "From"), "asunto": _cabecera(msg, "Subject"),
            "snippet": msg.get("snippet", ""),
            "etiquetas": [nombres.get(i, i) for i in msg.get("labelIds", [])]}


def buscar(svc, consulta: str, maximo: int) -> list[dict]:
    ids, token = [], None
    while len(ids) < maximo:
        r = svc.users().messages().list(userId="me", q=consulta, maxResults=min(100, maximo - len(ids)),
                                        **({"pageToken": token} if token else {})).execute()
        ids += [m["id"] for m in r.get("messages", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    nombres = {v: k for k, v in etiquetas(svc).items()}
    return [_resumen(svc.users().messages().get(userId="me", id=i, format="metadata",
                                                metadataHeaders=["From", "Subject"]).execute(), nombres)
            for i in ids[:maximo]]


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes, self._ignorar = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)


def _partes(payload: dict):
    yield payload
    for p in payload.get("parts", []) or []:
        yield from _partes(p)


def _decodificar(parte: dict) -> str:
    datos = parte.get("body", {}).get("data")
    return base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4)).decode("utf-8", "replace") if datos else ""


def leer(svc, id_: str, max_cuerpo: int) -> dict:
    msg = svc.users().messages().get(userId="me", id=id_, format="full").execute()
    partes = list(_partes(msg.get("payload", {})))
    plano = next((_decodificar(p) for p in partes if p.get("mimeType") == "text/plain" and _decodificar(p)), "")
    if not plano:
        html = next((_decodificar(p) for p in partes if p.get("mimeType") == "text/html"), "")
        t = _Texto()
        t.feed(html)
        plano = "".join(t.partes)
    cuerpo = " ".join(plano.split())
    if len(cuerpo) > max_cuerpo:
        cuerpo = cuerpo[:max_cuerpo] + "…"
    r = _resumen(msg, {v: k for k, v in etiquetas(svc).items()})
    r["cuerpo"] = cuerpo
    return r


def etiquetar(svc, cuenta: str, ids: list[str], poner: list[str], quitar: list[str],
              confirmado: bool) -> int:
    validar_cuenta(cuenta)
    mapa = etiquetas(svc)
    for nombre in poner + quitar:
        if nombre not in mapa:
            raise ValueError(f"etiqueta inexistente '{nombre}'; válidas: {', '.join(sorted(mapa))}")
    blanca = set(cargar_correo_cfg()["cuentas"][cuenta]["etiquetas_auto"])
    fuera = [n for n in poner if n not in blanca] + [n for n in quitar if n not in _SIN_CONFIRMAR_QUITAR]
    if fuera and not confirmado:
        raise Denegado(f"requiere confirmación del usuario (--confirmado) para: {', '.join(fuera)}")
    cuerpo = {"addLabelIds": [mapa[n] for n in poner], "removeLabelIds": [mapa[n] for n in quitar]}
    for i in ids:
        svc.users().messages().modify(userId="me", id=i, body=cuerpo).execute()
    return len(ids)


def borrador(svc, para: str, asunto: str, cuerpo: str, confirmado: bool) -> str:
    if not confirmado:
        raise Denegado("un borrador solo se crea si el usuario lo pide expresamente (--confirmado)")
    m = EmailMessage()
    m["To"], m["Subject"] = para, asunto
    m.set_content(cuerpo)
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    return svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()["id"]


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.google.gmail", allow_abbrev=False)
    sub = p.add_subparsers(dest="cmd", required=True)
    for nombre in ("buscar", "leer", "etiquetas", "etiquetar", "borrador"):
        s = sub.add_parser(nombre, allow_abbrev=False)
        s.add_argument("--cuenta", required=True, choices=CUENTAS)
        if nombre == "buscar":
            s.add_argument("--consulta", required=True)
            s.add_argument("--max", type=int, default=10)
        elif nombre == "leer":
            s.add_argument("--id", required=True)
        elif nombre == "etiquetar":
            s.add_argument("--ids", required=True, help="ids separados por comas")
            s.add_argument("--poner", default="")
            s.add_argument("--quitar", default="")
            s.add_argument("--confirmado", action="store_true")
        elif nombre == "borrador":
            s.add_argument("--para", required=True)
            s.add_argument("--asunto", required=True)
            s.add_argument("--cuerpo", required=True)
            s.add_argument("--confirmado", action="store_true")
    a = p.parse_args(argv)
    lista = lambda t: [x.strip() for x in t.split(",") if x.strip()]  # noqa: E731
    try:
        svc = servicio(a.cuenta, "gmail")
        if a.cmd == "buscar":
            r = buscar(svc, a.consulta, a.max)
        elif a.cmd == "leer":
            r = leer(svc, a.id, cargar_correo_cfg()["max_cuerpo"])
        elif a.cmd == "etiquetas":
            r = sorted(etiquetas(svc))
        elif a.cmd == "etiquetar":
            r = {"modificados": etiquetar(svc, a.cuenta, lista(a.ids), lista(a.poner), lista(a.quitar),
                                          a.confirmado)}
        else:
            r = {"borrador": borrador(svc, a.para, a.asunto, a.cuerpo, a.confirmado)}
    except Denegado as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 20
    except (CuentaNoAutorizada, ValueError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 21
    except Exception as e:  # HttpError de la API, etc.: mensaje legible, sin traceback
        print(json.dumps({"error": f"{type(e).__name__}: {e}"[:500]}, ensure_ascii=False))
        return 21
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

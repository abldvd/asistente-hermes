"""Cuentas de Google: un token OAuth por cuenta en secretos/google/.

Permisos mínimos: gmail.modify (leer, etiquetar, archivar, borradores) y calendar.events.
Ningún módulo del asistente usa el envío de correo.

CLI:
  python -m asistente.google.cuentas autorizar --cuenta seria
  python -m asistente.google.cuentas estado
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from asistente.estado import RAIZ

CUENTAS = ("seria", "personal")
SCOPES = ["https://www.googleapis.com/auth/gmail.modify",
          "https://www.googleapis.com/auth/calendar.events"]
_APIS = {"gmail": "v1", "calendar": "v3"}


class CuentaNoAutorizada(Exception):
    pass


def secretos_dir() -> Path:
    return Path(os.environ.get("ASISTENTE_SECRETOS") or RAIZ / "secretos" / "google")


def ruta_token(cuenta: str) -> Path:
    return secretos_dir() / f"token_{validar_cuenta(cuenta)}.json"


def validar_cuenta(cuenta: str) -> str:
    if cuenta not in CUENTAS:
        raise ValueError(f"cuenta desconocida '{cuenta}'; válidas: {', '.join(CUENTAS)}")
    return cuenta


def cargar_correo_cfg() -> dict:
    return json.loads((RAIZ / "config" / "correo.json").read_text(encoding="utf-8"))


def _credenciales(cuenta: str):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    ruta = ruta_token(cuenta)
    aviso = (f"la cuenta '{cuenta}' no está autorizada; ejecuta "
             f"`python -m asistente.google.cuentas autorizar --cuenta {cuenta}`")
    if not ruta.exists():
        raise CuentaNoAutorizada(aviso)
    try:
        creds = Credentials.from_authorized_user_file(str(ruta), SCOPES)
        if not creds.valid:
            if not creds.refresh_token:
                raise CuentaNoAutorizada(aviso)
            creds.refresh(Request())
            ruta.write_text(creds.to_json(), encoding="utf-8")
    except (RefreshError, ValueError) as e:
        raise CuentaNoAutorizada(f"{aviso} (token caducado o revocado: {type(e).__name__})") from e
    return creds


def servicio(cuenta: str, api: str):
    if api not in _APIS:
        raise ValueError(f"api desconocida '{api}'; válidas: {', '.join(_APIS)}")
    validar_cuenta(cuenta)
    from googleapiclient.discovery import build
    return build(api, _APIS[api], credentials=_credenciales(cuenta), cache_discovery=False)


def asegurar_permisos(carpeta: Path) -> None:
    """En Windows, deja la carpeta solo para el usuario actual y SYSTEM (sin herencia).

    Los archivos creados después heredan esos permisos. Falla si icacls no lo consigue.
    """
    if os.name != "nt":
        os.chmod(carpeta, 0o700)
        return
    usuario = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
    r = subprocess.run(["icacls", str(carpeta), "/inheritance:r", "/grant:r",
                        f"{usuario}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "/Q"],
                       capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OSError(f"no se pudieron restringir los permisos de {carpeta}: {(r.stderr or r.stdout).strip()}")


def _correo_de(creds) -> str:
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds, cache_discovery=False) \
        .users().getProfile(userId="me").execute()["emailAddress"]


def _enmascarar(correo: str) -> str:
    usuario, _, dominio = correo.partition("@")
    return f"{usuario[:2]}***@{dominio}"


def autorizar(cuenta: str) -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow

    validar_cuenta(cuenta)
    secreto = secretos_dir() / "client_secret.json"
    if not secreto.exists():
        raise FileNotFoundError(f"falta {secreto}")
    flow = InstalledAppFlow.from_client_secrets_file(str(secreto), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent select_account",
                                  authorization_prompt_message=f"Inicia sesión con la cuenta '{cuenta}': {{url}}",
                                  success_message="Autorizado. Puedes cerrar esta pestaña.")
    correo = _correo_de(creds)
    for otra in CUENTAS:
        if otra != cuenta and ruta_token(otra).exists():
            try:
                if _correo_de(_credenciales(otra)) == correo:
                    raise ValueError(f"esa cuenta ya está autorizada como '{otra}'; usa la otra cuenta")
            except CuentaNoAutorizada:
                pass
    ruta = ruta_token(cuenta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    asegurar_permisos(ruta.parent.parent if ruta.parent.name == "google" else ruta.parent)
    ruta.write_text(creds.to_json(), encoding="utf-8")
    return _enmascarar(correo)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.google.cuentas")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("autorizar")
    a.add_argument("--cuenta", required=True, choices=CUENTAS)
    sub.add_parser("estado")
    args = p.parse_args(argv)
    if args.cmd == "autorizar":
        try:
            print(f"AUTORIZADA {args.cuenta}: {autorizar(args.cuenta)}")
            return 0
        except (ValueError, OSError) as e:
            print(f"ERROR: {e}")
            return 21
    codigo = 0
    for c in CUENTAS:
        try:
            _credenciales(c)
            print(f"{c}: AUTORIZADA")
        except CuentaNoAutorizada as e:
            print(f"{c}: NO_AUTORIZADA ({e})")
            codigo = 21
    return codigo


if __name__ == "__main__":
    sys.exit(main())

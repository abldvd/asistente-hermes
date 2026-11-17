"""Hook `pre_tool_call` de Hermes: la confirmación de acciones sobre correo y calendario la da una
persona, no el modelo.

- Un comando de terminal con `--confirmado` o `asistente.sugerencias confirmar N` → se escala a la
  aprobación humana de Hermes ({"action": "approve"}), mostrando el comando o el evento real. En el
  cron no hay nadie que apruebe, así que falla cerrado.
- Leer `secretos/`, tocar tokens o importar las librerías de Google o los módulos del asistente desde
  código propio → se bloquea: la única vía son las CLI, que tienen sus reglas.

Falla cerrado: si el hook no puede decidir, bloquea.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys

from asistente import vales

_BLOQUEO = re.compile(
    r"secretos[\\/]|googleapiclient|google\.oauth2|google_auth_oauthlib|google\.auth\b"
    r"|token_(seria|personal)|client_secret|vales\.key|estado[\\/]+vales|[\\/]vales\b"
    r"|(?:estado|secr)[^\s]*[*?]|[*?][^\s]*(?:estado|secretos|vales)"
    r"|from\s+asistente(\.\w+)*\s+import|import\s+asistente",
    re.IGNORECASE)
# En código propio (execute_code o python -c) ni siquiera se permite nombrar estas cosas.
_CODIGO_PROHIBIDO = re.compile(r"asistente|importlib|__import__|secretos|secr['\"]|google|exec\(|eval\(",
                               re.IGNORECASE)
_PYTHON_C = re.compile(r"python(\.exe)?[\"']?\s+(-\w+\s+)*-c\b", re.IGNORECASE)
_CONFIRMADO = re.compile(r"--conf\w*", re.IGNORECASE)  # incluye abreviaturas
_CONFIRMAR_SUG = re.compile(r"asistente\.sugerencias\s+confirmar\s+(\d+)")
# Una única invocación limpia de una CLI del asistente, sin encadenar ni redirigir nada.
_UNA_INVOCACION = re.compile(
    r'^\s*(?:"?[A-Za-z]:[\\/][^"\s;&|<>`$]*python(?:\.exe)?"?|python(?:\.exe)?|PY)'
    r"\s+-m\s+asistente\.(?:google\.(?:gmail|calendario)|sugerencias)\s+"
    r"""[^;&|<>`$\r\n^%]*$""")
# Cualquier CLI del asistente (compuerta, correo_diario...), también una sola invocación limpia.
_INVOCACION_ASISTENTE = re.compile(
    r'^\s*(?:"?[A-Za-z]:[\\/][^"\s;&|<>`$]*python(?:\.exe)?"?|python(?:\.exe)?|PY)'
    r"\s+-m\s+asistente\.[\w.]+(?:\s+[^;&|<>`$\r\n^%]*)?$")
# "asistente" como módulo (no la carpeta E:\asistente-hermes), tras quitar lo que cmd ignora.
_MENCION = re.compile(r"asistente(?!-hermes)", re.IGNORECASE)
_OFUSCACION = re.compile(r'[\^`]|""')
_MAX_COMANDO = 1000
_OPCIONES_CON = {"--confirmado", "--consulta"}  # opciones reales que empiezan por --con
_TERMINAL = {"terminal", "shell", "bash", "powershell"}


def _textos(valor) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos(v)]
    if isinstance(valor, list):
        return [t for v in valor for t in _textos(v)]
    return []


def _detalle_sugerencia(n: int) -> str:
    try:
        from datetime import datetime

        from asistente.google.gmail import ZONA
        from asistente.sugerencias import detalle
        return detalle(n, datetime.now(ZONA))
    except Exception as e:  # se aprueba igual a ciegas no: el usuario ve que no hay detalle
        return f"sugerencia {n} (no se pudo leer el detalle: {type(e).__name__})"


def _bloquear(motivo: str) -> dict:
    return {"action": "block", "message": motivo}


def _visible(texto: str) -> str:
    """El comando tal cual, con los caracteres de control a la vista."""
    return "".join(c if c.isprintable() or c == " " else "\\x" + f"{ord(c):02x}" for c in texto)


def _bruto(args: list[str], nombre: str) -> str:
    """Valor completo de una opción: es el que se usa para decidir qué dice el resumen."""
    return args[args.index(nombre) + 1] if nombre in args and args.index(nombre) + 1 < len(args) else ""


def _ver(valor: str, limite: int = 120) -> str:
    """Solo para mostrar: una línea, controles a la vista y, si se recorta, con «…»."""
    v = _visible(" ".join(valor.split()))
    return v if len(v) <= limite else v[:limite] + "…"


def _resumen(modulo: str, args: list[str]) -> str:
    """Primera línea del aviso: qué va a pasar, en corto (Telegram recorta los avisos largos)."""
    cuenta = _ver(_bruto(args, "--cuenta"))
    sub = args[0] if args else ""
    if modulo == "asistente.google.gmail" and sub == "etiquetar":
        n = len([i for i in _bruto(args, "--ids").split(",") if i.strip()])
        poner = {x.strip() for x in _bruto(args, "--poner").split(",") if x.strip()}
        quitar = {x.strip() for x in _bruto(args, "--quitar").split(",") if x.strip()}
        acciones = [nombre for cond, nombre in [("TRASH" in poner, "mandar a la papelera"),
                                                ("SPAM" in poner, "marcar como spam"),
                                                ("INBOX" in quitar, "archivar")] if cond]
        otras = (poner - {"TRASH", "SPAM"}) | (quitar - {"INBOX"})
        if otras or not acciones:
            acciones.append(f"cambiar etiquetas (poner {_ver(','.join(sorted(poner - {'TRASH', 'SPAM'}))) or '-'}, "
                            f"quitar {_ver(','.join(sorted(quitar - {'INBOX'}))) or '-'}) de")
        que = " y ".join(acciones)
        return f"{que[0].upper()}{que[1:]} {n} correos de la cuenta {cuenta}."
    if modulo == "asistente.google.gmail" and sub == "borrador":
        return f"Crear un borrador para {_ver(_bruto(args, '--para'))} en la cuenta {cuenta}."
    if modulo == "asistente.google.calendario":
        if sub == "crear":
            return (f"Crear evento «{_ver(_bruto(args, '--titulo'))}» el {_ver(_bruto(args, '--inicio'))} "
                    f"en la cuenta {cuenta}.")
        if sub == "mover":
            return (f"Mover el evento {_ver(_bruto(args, '--id'))} al {_ver(_bruto(args, '--inicio'))} "
                    f"en la cuenta {cuenta}.")
        if sub == "borrar":
            return f"Borrar el evento {_ver(_bruto(args, '--id'))} de la cuenta {cuenta}."
    return "Acción que requiere tu aprobación."


def decidir(entrada: dict) -> dict | None:
    herramienta = str(entrada.get("tool_name") or "")
    texto = "\n".join(_textos(entrada.get("tool_input") or {}))
    if _BLOQUEO.search(texto):
        return _bloquear("Acceso directo a credenciales o a la API de Google no permitido. "
                         "Usa las CLI del asistente (skill correo-calendario).")
    if herramienta == "execute_code":
        return _bloquear("execute_code está desactivado en este asistente; usa la terminal con las CLI.")
    es_codigo = herramienta not in _TERMINAL or _PYTHON_C.search(texto)
    if es_codigo and _CODIGO_PROHIBIDO.search(texto):
        return _bloquear("Código propio que toca el asistente, Google o secretos no permitido; usa las CLI.")
    if herramienta in _TERMINAL and _MENCION.search(_OFUSCACION.sub("", texto)):
        # Falla cerrado: todo lo que toque el asistente es una invocación limpia, sin trucos de shell.
        comando = texto.strip()
        if any(not (c.isprintable() or c == " ") for c in comando):
            return _bloquear("Comando con caracteres de control no permitido.")
        if (_OFUSCACION.search(comando) or len(comando) > _MAX_COMANDO
                or len(_MENCION.findall(comando)) != 1 or not _INVOCACION_ASISTENTE.match(comando)):
            return _bloquear("Las CLI del asistente se lanzan solas, como UNA invocación limpia "
                             "(sin ^ ` \"\", sin encadenar ni redirigir, menos de 1000 caracteres).")
        try:
            tokens = shlex.split(comando, posix=False)
        except ValueError:
            return _bloquear("Comando con comillas desparejadas.")
        # Símbolos que bash (Git Bash) expandiría: --con{f,}irmado, --con?irmado...
        if re.search(r"[{}*?\[\]~!]", comando):
            return _bloquear("Los comandos del asistente no pueden llevar { } * ? [ ] ~ !")
        for t in tokens:
            # Lista blanca: una opción es exactamente -x o --palabra-con-guiones, en minúsculas.
            if t.lstrip("\"'\\").startswith("-") and not re.fullmatch(r"--?[a-z][a-z0-9-]*", t):
                return _bloquear("Opción con formato no permitido (sin comillas, barras ni mayúsculas).")
            if t.startswith("--con") and t not in _OPCIONES_CON:
                return _bloquear("Escribe la opción --confirmado tal cual, sin abreviar.")
        opciones = [t for t in tokens if t.startswith("-") and t != "-m"]
        if len(opciones) != len(set(opciones)):
            # argparse se queda con la última; el resumen del aviso podría mostrar otra.
            return _bloquear("Opción repetida en el comando; cada opción solo puede aparecer una vez.")
    confirmado = _CONFIRMADO.search(texto)
    sug = _CONFIRMAR_SUG.search(texto)
    if not (confirmado or sug):
        return None
    if herramienta not in _TERMINAL:
        return _bloquear("Las acciones con confirmación solo se pueden lanzar como comando de terminal.")
    comando = texto.strip()
    if len(comando) > _MAX_COMANDO or comando.count("asistente.") != 1 or not _UNA_INVOCACION.match(comando):
        return _bloquear("Una acción con confirmación debe ser UNA sola invocación de la CLI del asistente, "
                         "sin encadenar, redirigir ni otros comandos, y de menos de 1000 caracteres.")
    if confirmado and confirmado.group(0).lower() != "--confirmado":
        return _bloquear("Escribe la opción completa --confirmado.")
    partes = []
    if sug:
        partes.append(f"¿Crear este evento en el calendario?\n{_detalle_sugerencia(int(sug.group(1)))}")
    partes.append(f"Comando exacto:\n{_visible(comando)}")
    clave = hashlib.sha256(comando.encode("utf-8")).hexdigest()[:16]
    try:
        vales.emitir(*vales.argv_de(comando), regla=f"confirmado:{clave}")
    except Exception as e:
        return _bloquear(f"No se pudo emitir el vale de aprobación ({type(e).__name__}).")
    return {"action": "approve", "message": _resumen(*vales.argv_de(comando)) + "\n" + "\n\n".join(partes),
            "rule_key": f"confirmado:{clave}"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        r = decidir(json.loads(sys.stdin.read() or "{}"))
    except Exception as e:
        r = _bloquear(f"Hook de confirmación con error ({type(e).__name__}); acción bloqueada.")
    if r:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

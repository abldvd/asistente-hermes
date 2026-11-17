import io
import json

import pytest

from asistente import hook_confirmacion
from asistente.hook_confirmacion import decidir


def _e(tool, **args):
    return {"hook_event_name": "pre_tool_call", "tool_name": tool, "tool_input": args}


GM = r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.google.gmail"


def test_comando_normal_pasa():
    assert decidir(_e("terminal", command=f"{GM} buscar --cuenta seria --consulta x")) is None


def test_confirmado_pide_aprobacion_humana():
    cmd = f"{GM} etiquetar --cuenta seria --ids a,b --quitar INBOX --confirmado"
    r = decidir(_e("terminal", command=cmd))
    assert r["action"] == "approve" and "INBOX" in r["message"] and "seria" in r["message"]
    assert r["rule_key"].startswith("confirmado:")


def test_rule_key_distinta_por_comando():
    a = decidir(_e("terminal", command=f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirmado"))
    b = decidir(_e("terminal", command=f"{GM} etiquetar --cuenta seria --ids b --quitar INBOX --confirmado"))
    assert a["rule_key"] != b["rule_key"]


def test_confirmar_sugerencia_muestra_el_evento(monkeypatch):
    monkeypatch.setattr(hook_confirmacion, "_detalle_sugerencia", lambda n: f"Cita {n} — 2026-11-19T10:00")
    r = decidir(_e("terminal", command="python -m asistente.sugerencias confirmar 4"))
    assert r["action"] == "approve" and "Cita 4" in r["message"]


@pytest.mark.parametrize("tool,args", [
    ("read_file", {"path": r"E:\asistente-hermes\secretos\google\token_seria.json"}),
    ("terminal", {"command": "type E:\asistente-hermes\secretos\.env"}),
    ("terminal", {"command": "cat secretos/google/client_secret.json"}),
    ("execute_code", {"code": "from googleapiclient.discovery import build"}),
    ("execute_code", {"code": "from asistente.google.gmail import etiquetar; etiquetar(s,'seria',['a'],[],['INBOX'],True)"}),
    ("terminal", {"command": "python -c \"import asistente.google.calendario as c; c.borrar(s, 'x', True)\""}),
])
def test_acceso_directo_a_credenciales_o_api_se_bloquea(tool, args):
    assert decidir(_e(tool, **args))["action"] == "block"


def test_confirmado_en_execute_code_se_bloquea():
    assert decidir(_e("execute_code", code="subprocess.run(['python','-m','asistente.google.gmail','etiquetar','--confirmado'])"))["action"] == "block"


def test_main_falla_cerrado(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{roto"))
    assert hook_confirmacion.main() == 0
    assert json.loads(capsys.readouterr().out)["action"] == "block"


def test_main_sin_salida_si_pasa(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_e("terminal", command="dir"))))
    assert hook_confirmacion.main() == 0 and capsys.readouterr().out == ""

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


@pytest.mark.parametrize("cmd", [
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --conf",        # abreviatura
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirm",
])
def test_abreviaturas_de_confirmado_tambien_piden_aprobacion_o_bloquean(cmd):
    assert decidir(_e("terminal", command=cmd))["action"] in ("approve", "block")


@pytest.mark.parametrize("cmd", [
    f"{GM} buscar --cuenta seria --consulta x; {GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirmado",
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirmado & del x",
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirmado | more",
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --confirmado\n{GM} borrador --confirmado",
    "python -m asistente.sugerencias confirmar 2 && python -m asistente.google.gmail etiquetar --confirmado",
    f"{GM} etiquetar --cuenta seria --ids {'a,' * 600} --quitar INBOX --confirmado",  # demasiado largo
])
def test_encadenados_o_demasiado_largos_se_bloquean(cmd):
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


def test_aprobacion_muestra_el_comando_completo():
    cmd = f"{GM} etiquetar --cuenta personal --ids a,b,c --poner TRASH --confirmado"
    assert cmd in decidir(_e("terminal", command=cmd))["message"]


def test_sugerencia_muestra_detalle_y_comando(monkeypatch):
    monkeypatch.setattr(hook_confirmacion, "_detalle_sugerencia", lambda n: "Cita X")
    cmd = r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.sugerencias confirmar 4"
    m = decidir(_e("terminal", command=cmd))["message"]
    assert "Cita X" in m and cmd in m


@pytest.mark.parametrize("tool,args", [
    ("execute_code", {"code": "import importlib; m = importlib.import_module('asist' + 'ente')"}),
    ("execute_code", {"code": "__import__('asistente')"}),
    ("execute_code", {"code": "open('E:/asistente-hermes/secr' + 'etos/x')"}),
    ("terminal", {"command": "python -c \"import importlib\""}),
    ("terminal", {"command": "python -c \"__import__('os')\""}),
])
def test_evasiones_por_codigo_se_bloquean(tool, args):
    assert decidir(_e(tool, **args))["action"] == "block"


def test_todas_las_cli_rechazan_abreviaturas(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(tmp_path))  # nunca tocar las cuentas reales
    from asistente import claude_tope, compuerta, openrouter, sugerencias
    from asistente.google import calendario, cuentas, gmail
    for mod, argv in [(gmail, ["etiquetar", "--cuenta", "seria", "--ids", "a", "--quitar", "INBOX", "--conf"]),
                      (calendario, ["borrar", "--cuenta", "seria", "--id", "x", "--conf"]),
                      (sugerencias, ["listar", "--x"]),
                      (cuentas, ["estado", "--x"]),
                      (claude_tope, ["--perf", "web"]),
                      (openrouter, ["--prompt", "f"]),
                      (compuerta, ["--tar", "x"])]:
        with pytest.raises(SystemExit):
            mod.main(argv)


@pytest.mark.parametrize("cmd", [
    f'{GM} etiquetar --cuenta seria --ids a --quitar INBOX "--confirmado"',     # comillas alrededor
    f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --con^firmado",      # escape de cmd
    f'{GM} etiquetar --cuenta seria --ids a --quitar INBOX --con""firmado',     # comillas vacías
    "python -m asis^tente.google.gmail etiquetar --cuenta seria --confirmado",
    'python -m "asistente.google.gmail" etiquetar --cuenta seria --ids a --quitar INBOX --confirmado',
])
def test_ofuscaciones_del_comando_se_bloquean(cmd):
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


def test_cualquier_mencion_del_asistente_debe_ser_invocacion_limpia():
    assert decidir(_e("terminal", command=f"echo hola & {GM} buscar --cuenta seria --consulta x"))["action"] == "block"
    assert decidir(_e("terminal", command=f'{GM} buscar --cuenta seria --consulta "from:x newer_than:7d"')) is None
    assert decidir(_e("terminal", command=r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.compuerta --tarea chat")) is None


def test_execute_code_se_bloquea_siempre():
    assert decidir(_e("execute_code", code="print(1)"))["action"] == "block"


@pytest.mark.parametrize("flag", ['--con"fi"rmado', "--con'fi'rmado", '--"confirmado"', '-"-confirmado"',
                                  "--con\firmado", '--confirmad"o"'])
def test_comillas_dentro_de_una_opcion_se_bloquean(flag):
    cmd = f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX {flag}"
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


def test_valor_entre_comillas_sigue_permitido():
    cmd = f'{GM} etiquetar --cuenta seria --ids a --poner "Empleo"'
    assert decidir(_e("terminal", command=cmd)) is None


def test_barra_literal_en_opcion_se_bloquea():
    cmd = f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX --con" + chr(92) + "firmado"
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


def test_caracteres_de_control_se_bloquean():
    cmd = f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX\x0c--confirmado"
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


@pytest.mark.parametrize("flag", ["--con{f,}irmado", "--con?irmado", "--con*", "--c[o]nfirmado",
                                  "--confirmad~", "--conf!rmado", "--Confirmado", "--con_firmado"])
def test_expansiones_de_bash_y_opciones_raras_se_bloquean(flag):
    cmd = f"{GM} etiquetar --cuenta seria --ids a --quitar INBOX {flag}"
    assert decidir(_e("terminal", command=cmd))["action"] == "block"


def test_valores_con_simbolos_de_bash_se_bloquean():
    assert decidir(_e("terminal", command=f'{GM} buscar --cuenta seria --consulta "a*"'))["action"] == "block"

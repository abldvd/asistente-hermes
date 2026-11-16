import io
import json
from datetime import date

from asistente import tope_delegacion
from asistente.tope_delegacion import decidir
from asistente.uso import Uso, llamadas_hoy, registrar_llamada

OK = Uso(10, True)


def _entrada(**tool_input):
    return {"hook_event_name": "pre_tool_call", "tool_name": "delegate_task", "tool_input": tool_input}


def test_permite_y_cuenta_una_por_subtarea():
    bloquear, _, n = decidir(_entrada(tasks=[{"goal": "a"}, {"goal": "b"}]), OK, 0, 10, 80)
    assert (bloquear, n) == (False, 2)


def test_acciones_sin_tareas_nuevas_no_cuentan():
    for accion in ("list", "steer", "stop"):
        assert decidir(_entrada(action=accion), Uso(None, False), 10, 10, 80)[:2] == (False, "")


def test_bloquea_con_cuota_alta():
    bloquear, msg, n = decidir(_entrada(tasks=[{"goal": "a"}]), Uso(85, True), 0, 10, 80)
    assert bloquear and n == 0 and "85" in msg and "local" in msg


def test_bloquea_con_dato_de_uso_desfasado():
    assert decidir(_entrada(tasks=[{"goal": "a"}]), Uso(10, False), 0, 10, 80)[0] is True


def test_bloquea_si_el_lote_supera_lo_que_queda_del_tope():
    bloquear, msg, _ = decidir(_entrada(tasks=[{"goal": "a"}, {"goal": "b"}]), OK, 9, 10, 80)
    assert bloquear and "9/10" in msg


def test_tool_input_raro_cuenta_como_una():
    assert decidir(_entrada(goal="x"), OK, 0, 10, 80) == (False, "", 1)
    assert decidir({"tool_name": "delegate_task", "tool_input": None}, OK, 0, 10, 80) == (False, "", 1)


def test_main_registra_llamadas_y_no_imprime_nada(monkeypatch, capsys):
    monkeypatch.setattr(tope_delegacion, "_uso_actual", lambda cfg: OK)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_entrada(tasks=[{"goal": "a"}, {"goal": "b"}]))))
    assert tope_delegacion.main() == 0
    assert capsys.readouterr().out == ""
    assert llamadas_hoy(date.today()) == 2


def test_main_bloquea_con_json_y_no_registra(monkeypatch, capsys):
    for _ in range(10):
        registrar_llamada(date.today())
    monkeypatch.setattr(tope_delegacion, "_uso_actual", lambda cfg: OK)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_entrada(tasks=[{"goal": "a"}]))))
    assert tope_delegacion.main() == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida["action"] == "block" and "tope diario" in salida["message"]
    assert llamadas_hoy(date.today()) == 10


def test_main_con_stdin_ilegible_bloquea(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{roto"))
    assert tope_delegacion.main() == 0
    assert json.loads(capsys.readouterr().out)["action"] == "block"

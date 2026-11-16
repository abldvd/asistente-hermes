import io
import json

from asistente import aviso_juego
from asistente.aviso_juego import decidir


def _entrada(msg, **extra):
    return {"hook_event_name": "pre_llm_call", "extra": {"user_message": msg, **extra}}


def test_sin_juego_no_bloquea():
    assert decidir(_entrada("hola"), juego=False) is None


def test_con_juego_bloquea_y_explica_como_forzar():
    msg = decidir(_entrada("hola"), juego=True)
    assert "juego abierto" in msg and "!" in msg


def test_con_juego_y_exclamacion_pasa():
    assert decidir(_entrada("  !resume esto"), juego=True) is None


def test_subagente_no_se_bloquea():
    # los hijos de delegate_task van a Claude, no a la GPU
    assert decidir(_entrada("x", parent_session_id="abc"), juego=True) is None


def test_mensaje_ausente_con_juego_bloquea():
    assert decidir({"extra": {}}, juego=True) is not None


def test_main_imprime_bloqueo(monkeypatch, capsys):
    monkeypatch.setattr(aviso_juego, "_hay_juego", lambda: True)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_entrada("hola"))))
    assert aviso_juego.main() == 0
    assert json.loads(capsys.readouterr().out)["action"] == "block"


def test_main_falla_abierto(monkeypatch, capsys):
    # si la comprobación falla, mejor responder que dejar al usuario sin bot
    monkeypatch.setattr("sys.stdin", io.StringIO("{roto"))
    assert aviso_juego.main() == 0
    assert capsys.readouterr().out == ""

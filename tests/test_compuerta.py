from datetime import datetime

from asistente import compuerta
from asistente.compuerta import decidir

D = datetime(2026, 11, 16)


def h(hora, minuto=0, dia=16):
    return datetime(2026, 11, dia, hora, minuto)


def test_estado_vacio_sin_impedimentos_ejecuta():
    assert decidir("t", h(8), False, True, {}, 4)[0] == "EJECUTAR"


def test_juego_espera_y_registra_primer_intento():
    decision, est = decidir("t", h(8), True, True, {}, 4)
    assert decision == "ESPERAR"
    assert est["primer_intento"] == h(8).isoformat()


def test_falta_cuota_espera():
    assert decidir("t", h(8), False, False, {}, 4)[0] == "ESPERAR"


def test_pasado_el_maximo_se_salta_y_luego_ya_saltado():
    _, est = decidir("t", h(8), True, True, {}, 4)
    decision, est = decidir("t", h(12, 1), True, True, est, 4)
    assert decision == "SALTAR" and est["saltado"] is True
    assert decidir("t", h(12, 31), True, True, est, 4)[0] == "YA_SALTADO"


def test_hecho_hoy():
    est = {"fecha": "2026-11-16", "primer_intento": None, "hecho": True, "saltado": False}
    assert decidir("t", h(9), False, True, est, 4)[0] == "HECHO"


def test_saltado_ayer_no_bloquea_hoy():
    est = {"fecha": "2026-11-15", "primer_intento": "2026-11-15T08:00:00", "hecho": False, "saltado": True}
    assert decidir("t", h(8), False, True, est, 4)[0] == "EJECUTAR"


def test_retraso_que_cruza_medianoche():
    _, est = decidir("t", datetime(2026, 11, 15, 23, 0), True, True, {}, 4)
    assert decidir("t", h(0, 30), False, True, est, 4)[0] == "EJECUTAR"


def test_cli_codigos_y_marcar_hecho(monkeypatch, capsys):
    monkeypatch.setattr(compuerta, "_hay_juego_ahora", lambda cfg: False)
    assert compuerta.main(["--tarea", "prueba"]) == 0
    assert "DECISION: EJECUTAR" in capsys.readouterr().out
    assert compuerta.main(["--tarea", "prueba", "--hecho"]) == 0
    assert compuerta.main(["--tarea", "prueba"]) == 12
    monkeypatch.setattr(compuerta, "_hay_juego_ahora", lambda cfg: True)
    assert compuerta.main(["--tarea", "otra"]) == 10

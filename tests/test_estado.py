from asistente import estado


def test_leer_json_ausente_devuelve_defecto():
    assert estado.leer_json("x", {"a": 1}) == {"a": 1}


def test_ida_y_vuelta():
    estado.escribir_json("x", {"n": 2})
    assert estado.leer_json("x", None) == {"n": 2}


def test_json_corrupto_devuelve_defecto(estado_temporal):
    (estado_temporal / "x.json").write_text("{no", encoding="utf-8")
    assert estado.leer_json("x", {"d": 0}) == {"d": 0}


def test_escritura_atomica_no_deja_tmp(estado_temporal):
    estado.escribir_json("x", {"n": 1})
    assert list(estado_temporal.glob("*.tmp")) == []


def test_cargar_config_lee_tope():
    assert estado.cargar_config()["tope_claude_diario"] == 10

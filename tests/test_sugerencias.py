import json
from datetime import datetime

import pytest

from asistente import sugerencias
from asistente.estado import estado_dir, leer_json
from asistente.google.gmail import ZONA

AHORA = datetime(2026, 11, 17, 8, 0, tzinfo=ZONA)


@pytest.fixture
def cal(monkeypatch):
    estado = {"existentes": set(), "creados": []}
    monkeypatch.setattr(sugerencias, "servicio", lambda cuenta, api: cuenta)
    monkeypatch.setattr(sugerencias, "existe_parecido",
                        lambda svc, titulo, inicio: (svc, titulo) in estado["existentes"])
    def crear(svc, titulo, inicio, fin, descripcion="", confirmado=False):
        estado["creados"].append((svc, titulo, inicio, fin, confirmado))
        return {"id": "e1", "titulo": titulo, "inicio": inicio, "fin": fin}
    monkeypatch.setattr(sugerencias, "crear", crear)
    return estado


def _s(titulo="Entrevista DataCanarias", inicio="2026-11-19T10:00", cuenta="seria", **kw):
    return {"cuenta": cuenta, "titulo": titulo, "inicio": inicio, "origen_id": "m1", **kw}


def test_agregar_numera_y_guarda(cal):
    nuevas = sugerencias.agregar([_s(), _s("Plazo beca", "2026-11-20T23:59", fin="2026-11-21T00:30")], AHORA)
    assert [n["n"] for n in nuevas] == [1, 2]
    assert nuevas[0]["fin"] == "2026-11-19T11:00:00+00:00"  # sin fin: 1 hora
    assert len(leer_json("sugerencias", [])) == 2


def test_no_duplica_misma_cita(cal):
    sugerencias.agregar([_s()], AHORA)
    assert sugerencias.agregar([_s("entrevista  datacanarias")], AHORA) == []


def test_descarta_si_ya_esta_en_calendario(cal):
    cal["existentes"].add(("seria", "Entrevista DataCanarias"))
    assert sugerencias.agregar([_s()], AHORA) == []


def test_descarta_pasadas(cal):
    assert sugerencias.agregar([_s(inicio="2026-11-16T10:00")], AHORA) == []


def test_listar_caduca_las_pasadas(cal):
    sugerencias.agregar([_s()], AHORA)
    assert sugerencias.listar(datetime(2026, 11, 20, tzinfo=ZONA)) == []


def test_confirmar_crea_en_la_cuenta_de_origen(cal):
    sugerencias.agregar([_s(cuenta="personal")], AHORA)
    ev = sugerencias.confirmar(1, AHORA)
    assert cal["creados"] == [("personal", "Entrevista DataCanarias", "2026-11-19T10:00:00+00:00",
                               "2026-11-19T11:00:00+00:00", True)]
    assert ev["id"] == "e1" and sugerencias.listar(AHORA) == []


def test_confirmar_numero_inexistente(cal):
    sugerencias.agregar([_s()], AHORA)
    with pytest.raises(KeyError) as e:
        sugerencias.confirmar(7, AHORA)
    assert "1" in str(e.value)


def test_descartar(cal):
    sugerencias.agregar([_s()], AHORA)
    sugerencias.descartar(1)
    assert sugerencias.listar(AHORA) == [] and cal["creados"] == []


def test_sugerencia_invalida_se_ignora(cal):
    assert sugerencias.agregar([_s(cuenta="otra"), _s(inicio="jueves"), {"titulo": "x"}], AHORA) == []


def test_json_file_fuera_de_su_carpeta(tmp_path, cal, capsys):
    f = tmp_path / "x.json"
    f.write_text(json.dumps([_s()]), encoding="utf-8")
    assert sugerencias.main(["agregar", "--json-file", str(f)]) == 20


def test_cli_agregar_desde_su_carpeta(cal, capsys):
    d = estado_dir() / "sugerencias_in"
    d.mkdir(parents=True, exist_ok=True)
    (d / "lote.json").write_text(json.dumps([_s(inicio="2099-01-01T10:00")]), encoding="utf-8")
    assert sugerencias.main(["agregar", "--json-file", str(d / "lote.json")]) == 0
    assert json.loads(capsys.readouterr().out)[0]["n"] == 1


def test_cli_confirmar_inexistente_da_20(cal, capsys):
    assert sugerencias.main(["confirmar", "3"]) == 20

import json

import pytest

from asistente.google import calendario
from asistente.google.calendario import a_rfc3339, borrar, crear, existe_parecido, listar, mover
from asistente.google.gmail import Denegado


class _Llamada:
    def __init__(self, r):
        self._r = r

    def execute(self):
        return self._r


class FakeCal:
    def __init__(self, eventos=None):
        self.eventos = eventos or []
        self.llamadas = []

    def events(self):
        return self

    def list(self, **kw):
        self.llamadas.append(("list", kw))
        return _Llamada({"items": self.eventos})

    def insert(self, **kw):
        self.llamadas.append(("insert", kw))
        return _Llamada({"id": "e1", **kw["body"]})

    def patch(self, **kw):
        self.llamadas.append(("patch", kw))
        return _Llamada({"id": kw["eventId"]})

    def delete(self, **kw):
        self.llamadas.append(("delete", kw))
        return _Llamada("")


def _evento(titulo, inicio):
    return {"id": "x", "summary": titulo, "start": {"dateTime": inicio}, "end": {"dateTime": inicio}}


def test_hora_local_en_invierno_y_verano():
    assert a_rfc3339("2026-01-15T10:00") == "2026-01-15T10:00:00+00:00"
    assert a_rfc3339("2026-07-15T10:00") == "2026-07-15T10:00:00+01:00"


def test_cambio_de_hora_octubre():
    assert a_rfc3339("2026-10-24T10:00") == "2026-10-24T10:00:00+01:00"
    assert a_rfc3339("2026-10-25T10:00") == "2026-10-25T10:00:00+00:00"


def test_desfase_explicito_se_respeta():
    assert a_rfc3339("2026-07-15T10:00:00+02:00") == "2026-07-15T10:00:00+02:00"
    assert a_rfc3339("2026-07-15T10:00:00Z") == "2026-07-15T10:00:00+00:00"


@pytest.mark.parametrize("malo", ["mañana a las 10", "15/07/2026 10:00", "2026-07-15", ""])
def test_formato_invalido_se_rechaza(malo):
    with pytest.raises(ValueError):
        a_rfc3339(malo)


def test_crear_mover_borrar_exigen_confirmado():
    svc = FakeCal()
    with pytest.raises(Denegado):
        crear(svc, "Cita", "2026-07-15T10:00", "2026-07-15T11:00")
    with pytest.raises(Denegado):
        mover(svc, "e1", "2026-07-15T10:00", "2026-07-15T11:00")
    with pytest.raises(Denegado):
        borrar(svc, "e1")
    assert svc.llamadas == []


def test_crear_envia_zona():
    svc = FakeCal()
    crear(svc, "Cita", "2026-07-15T10:00", "2026-07-15T11:00", confirmado=True)
    body = svc.llamadas[0][1]["body"]
    assert body["start"] == {"dateTime": "2026-07-15T10:00:00+01:00", "timeZone": "Atlantic/Canary"}
    assert body["summary"] == "Cita"


def test_fin_anterior_al_inicio_se_rechaza():
    with pytest.raises(ValueError):
        crear(FakeCal(), "Cita", "2026-07-15T11:00", "2026-07-15T10:00", confirmado=True)


def test_listar_devuelve_campos_simples():
    svc = FakeCal([_evento("Dentista", "2026-07-15T10:00:00+01:00")])
    assert listar(svc, "2026-07-15T00:00", "2026-07-16T00:00") == [
        {"id": "x", "titulo": "Dentista", "inicio": "2026-07-15T10:00:00+01:00",
         "fin": "2026-07-15T10:00:00+01:00"}]


def test_existe_parecido():
    svc = FakeCal([_evento("Entrevista técnica con DataCanarias", "2026-07-15T10:00:00+01:00")])
    assert existe_parecido(svc, "entrevista tecnica con datacanarias", "2026-07-15T10:30")
    assert existe_parecido(svc, "Entrevista técnica", "2026-07-15T10:00")
    assert not existe_parecido(FakeCal([_evento("Dentista", "2026-07-15T10:00:00+01:00")]),
                               "Entrevista", "2026-07-15T10:00")


def test_cli_crear_sin_confirmar_da_20(monkeypatch, capsys):
    monkeypatch.setattr(calendario, "servicio", lambda c, a: FakeCal())
    codigo = calendario.main(["crear", "--cuenta", "personal", "--titulo", "X",
                              "--inicio", "2026-07-15T10:00", "--fin", "2026-07-15T11:00"])
    assert codigo == 20 and "confirm" in json.loads(capsys.readouterr().out)["error"]

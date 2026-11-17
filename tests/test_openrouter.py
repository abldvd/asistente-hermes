import io
import json

import pytest

from asistente import openrouter


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def clave(monkeypatch):
    monkeypatch.setattr(openrouter, "_clave", lambda: "sk-test")


def test_pregunta_devuelve_el_texto_y_usa_el_modelo_configurado(monkeypatch, clave):
    enviados = []
    def urlopen(req, timeout):
        enviados.append(json.loads(req.data))
        return _Resp(json.dumps({"choices": [{"message": {"content": "4"}}]}).encode())
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", urlopen)
    assert openrouter.preguntar("2+2", modelos=["m1"]) == (0, "4")
    assert enviados[0]["model"] == "m1" and enviados[0]["messages"][-1]["content"] == "2+2"


def test_si_el_primero_falla_prueba_el_siguiente(monkeypatch, clave):
    usados = []
    def urlopen(req, timeout):
        m = json.loads(req.data)["model"]
        usados.append(m)
        if m == "m1":
            raise OSError("429")
        return _Resp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", urlopen)
    assert openrouter.preguntar("x", modelos=["m1", "m2"]) == (0, "ok") and usados == ["m1", "m2"]


def test_todos_fallan_da_error_legible(monkeypatch, clave):
    def urlopen(req, timeout):
        raise OSError("429 rate limit")
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", urlopen)
    codigo, msg = openrouter.preguntar("x", modelos=["m1"])
    assert codigo == 21 and "429" in msg and "sk-test" not in msg


def test_no_envia_secretos(monkeypatch, clave):
    monkeypatch.setattr(openrouter, "contiene_secreto", lambda p: True)
    monkeypatch.setattr(openrouter.urllib.request, "urlopen", lambda *a, **k: pytest.fail("no debe llamar"))
    assert openrouter.preguntar("x", modelos=["m1"])[0] == 20


def test_sin_clave(monkeypatch):
    monkeypatch.setattr(openrouter, "_clave", lambda: None)
    assert openrouter.preguntar("x", modelos=["m1"])[0] == 20

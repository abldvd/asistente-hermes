import json
from datetime import datetime

import pytest

from asistente import correo_auto
from asistente.estado import leer_json
from asistente.google.gmail import ZONA

AHORA = datetime(2026, 11, 17, 8, 0, tzinfo=ZONA)
LOTES = [{"cuenta": "seria", "correos": [{"id": "m1", "de": "a", "asunto": "x", "fecha": "f", "etiquetas": [], "cuerpo": "c"}],
          "omitidos": 0, "hasta_ts": 10},
         {"cuenta": "personal", "correos": [{"id": "p1", "de": "b", "asunto": "y", "fecha": "f", "etiquetas": [], "cuerpo": "c"}],
          "omitidos": 0, "hasta_ts": 20}]


@pytest.fixture
def entorno(monkeypatch):
    reg = {"etiquetas": [], "sugerencias": [], "cerrado": False}
    monkeypatch.setattr(correo_auto, "_compuerta", lambda: ("EJECUTAR", ""))
    monkeypatch.setattr(correo_auto, "recolectar_todo", lambda ahora: (LOTES, {"seria": 10, "personal": 20}))
    monkeypatch.setattr(correo_auto, "servicio", lambda c, a: c)
    def etiquetar(svc, cuenta, ids, poner, quitar, confirmado):
        assert confirmado is False and quitar == []
        reg["etiquetas"].append((cuenta, tuple(ids), tuple(poner)))
        return len(ids)
    monkeypatch.setattr(correo_auto, "etiquetar", etiquetar)
    def agregar(items, ahora):
        reg["sugerencias"] += items
        return [{**it, "n": i + 1, "inicio": "2026-11-19T10:00:00+00:00"} for i, it in enumerate(items)]
    monkeypatch.setattr(correo_auto, "agregar", agregar)
    monkeypatch.setattr(correo_auto, "cerrar_lote", lambda: reg.__setitem__("cerrado", True))
    return reg


def _modelo(respuesta):
    return lambda mensajes: json.dumps(respuesta)


def test_aplica_solo_etiquetas_de_la_lista_blanca_e_ids_del_lote(entorno):
    r = {"resumen": "Hola", "etiquetas": [
        {"cuenta": "seria", "id": "m1", "etiqueta": "Empleo"},
        {"cuenta": "seria", "id": "m1", "etiqueta": "TRASH"},          # fuera de lista
        {"cuenta": "seria", "id": "otro", "etiqueta": "Empleo"},       # id ajeno al lote
        {"cuenta": "personal", "id": "m1", "etiqueta": "Juegos"},      # id de otra cuenta
        {"cuenta": "personal", "id": "p1", "etiqueta": "Juegos"}], "eventos": []}
    correo_auto.ejecutar(AHORA, _modelo(r))
    assert sorted(entorno["etiquetas"]) == [("personal", ("p1",), ("Juegos",)), ("seria", ("m1",), ("Empleo",))]


def test_sugerencias_solo_de_correos_del_lote_y_mensaje_con_numeros(entorno):
    r = {"resumen": "Resumen del día", "etiquetas": [], "eventos": [
        {"cuenta": "seria", "titulo": "Entrevista", "inicio": "2026-11-19T10:00", "origen_id": "m1"},
        {"cuenta": "seria", "titulo": "Falsa", "inicio": "2026-11-19T10:00", "origen_id": "zzz"}]}
    msg = correo_auto.ejecutar(AHORA, _modelo(r))
    assert [s["titulo"] for s in entorno["sugerencias"]] == ["Entrevista"]
    assert "Resumen del día" in msg and "1. Entrevista" in msg and "añade 1" in msg
    assert entorno["cerrado"] is True


def test_el_modelo_no_recibe_herramientas(entorno):
    vistos = []
    def modelo(mensajes):
        vistos.append(mensajes)
        return json.dumps({"resumen": "r", "etiquetas": [], "eventos": []})
    correo_auto.ejecutar(AHORA, modelo)
    assert all(set(m) <= {"role", "content"} for m in vistos[0])


def test_json_invalido_no_cierra_y_avisa_una_vez(entorno):
    m1 = correo_auto.ejecutar(AHORA, lambda m: "no es json")
    m2 = correo_auto.ejecutar(AHORA, lambda m: "no es json")
    assert "no pude" in m1.lower() and m2 == "" and entorno["cerrado"] is False


def test_esperar_es_silencioso(monkeypatch):
    monkeypatch.setattr(correo_auto, "_compuerta", lambda: ("ESPERAR", "juego abierto"))
    assert correo_auto.ejecutar(AHORA, lambda m: pytest.fail("no")) == ""


def test_saltar_avisa(monkeypatch):
    monkeypatch.setattr(correo_auto, "_compuerta", lambda: ("SALTAR", "juego abierto"))
    assert "juego abierto" in correo_auto.ejecutar(AHORA, lambda m: pytest.fail("no"))


def test_sin_correos_cierra_en_silencio(monkeypatch, entorno):
    monkeypatch.setattr(correo_auto, "recolectar_todo", lambda ahora: (
        [{"cuenta": "seria", "correos": [], "omitidos": 0, "hasta_ts": 1}], {"seria": 1}))
    assert correo_auto.ejecutar(AHORA, lambda m: pytest.fail("no")) == "" and entorno["cerrado"]


def test_error_de_cuenta_aparece_en_el_mensaje(monkeypatch, entorno):
    monkeypatch.setattr(correo_auto, "recolectar_todo", lambda ahora: (
        [LOTES[0], {"cuenta": "personal", "error": "hay que volver a autorizarla"}], {"seria": 10}))
    msg = correo_auto.ejecutar(AHORA, _modelo({"resumen": "r", "etiquetas": [], "eventos": []}))
    assert "personal" in msg and "autorizarla" in msg


def test_error_inesperado_avisa_una_vez_al_dia(monkeypatch):
    monkeypatch.setattr(correo_auto, "_compuerta", lambda: (_ for _ in ()).throw(AttributeError("x")))
    assert "no pude" in correo_auto.ejecutar_seguro(AHORA).lower()
    assert correo_auto.ejecutar_seguro(AHORA) == ""


def test_resumen_vacio_no_cierra(entorno):
    msg = correo_auto.ejecutar(AHORA, _modelo({"resumen": "  ", "etiquetas": [], "eventos": []}))
    assert entorno["cerrado"] is False and "no pude" in msg.lower()


def test_la_cuenta_de_la_sugerencia_es_la_del_correo(entorno):
    r = {"resumen": "r", "etiquetas": [], "eventos": [
        {"cuenta": "personal", "titulo": "Cita", "inicio": "2026-11-19T10:00", "origen_id": "m1"}]}  # m1 es de seria
    correo_auto.ejecutar(AHORA, _modelo(r))
    assert entorno["sugerencias"][0]["cuenta"] == "seria"


def test_correo_diario_ya_no_tiene_cli():
    from asistente import correo_diario
    assert not hasattr(correo_diario, "main")

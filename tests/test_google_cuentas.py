import pytest

from asistente.google import cuentas
from asistente.google.cuentas import (CuentaNoAutorizada, SCOPES, cargar_correo_cfg, ruta_token,
                                      servicio, validar_cuenta)


def test_scopes_no_incluyen_envio():
    assert SCOPES == ["https://www.googleapis.com/auth/gmail.modify",
                      "https://www.googleapis.com/auth/calendar.events"]
    assert not any("gmail.send" in s or s.rstrip("/").endswith("mail.google.com") for s in SCOPES)


def test_cuenta_desconocida():
    with pytest.raises(ValueError):
        validar_cuenta("otra")
    assert validar_cuenta("seria") == "seria"


def test_ruta_token_en_secretos(monkeypatch):
    monkeypatch.delenv("ASISTENTE_SECRETOS", raising=False)
    assert ruta_token("seria").as_posix().endswith("secretos/google/token_seria.json")


def test_ruta_token_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(tmp_path))
    assert ruta_token("personal") == tmp_path / "token_personal.json"


def test_servicio_sin_token_lanza_cuenta_no_autorizada(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(tmp_path))
    with pytest.raises(CuentaNoAutorizada) as e:
        servicio("seria", "gmail")
    assert "autorizar --cuenta seria" in str(e.value)


def test_servicio_api_desconocida():
    with pytest.raises(ValueError):
        servicio("seria", "drive")


def test_config_correo_tiene_lista_blanca():
    cfg = cargar_correo_cfg()
    assert cfg["cuentas"]["seria"]["etiquetas_auto"] == ["Empleo", "Newsletters", "Música"]
    assert cfg["cuentas"]["personal"]["etiquetas_auto"] == [
        "GitHub", "Juegos", "Música", "Newsletters", "Redes/Facebook"]
    assert (cfg["max_correos"], cfg["max_cuerpo"], cfg["primera_ventana_h"]) == (40, 1200, 24)
    assert set(cfg["cuentas"]) == set(cuentas.CUENTAS)

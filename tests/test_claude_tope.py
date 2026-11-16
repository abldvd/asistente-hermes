import json
import subprocess
from datetime import date
from types import SimpleNamespace

import pytest

from asistente import claude_tope
from asistente.claude_tope import construir_comando, ejecutar
from asistente.uso import Uso, llamadas_hoy

PERFIL = {"allowedTools": "WebSearch,WebFetch", "max_turns": 8, "model": "sonnet"}


def test_comando_acotado_y_sin_saltarse_permisos():
    cmd = construir_comando(PERFIL)
    assert cmd[:2] == ["claude", "-p"]
    i = cmd.index("--max-turns"); assert cmd[i + 1] == "8"
    i = cmd.index("--output-format"); assert cmd[i + 1] == "json"
    i = cmd.index("--tools"); assert cmd[i + 1] == PERFIL["allowedTools"]
    assert "--strict-mcp-config" in cmd
    assert not any("dangerously" in c or "bypassPermissions" in c for c in cmd)


@pytest.fixture
def cuota(monkeypatch):
    def poner(u):
        monkeypatch.setattr(claude_tope, "leer_uso", lambda *a, **k: u)
    poner(Uso(10, True))
    return poner


def test_cuota_agotada_no_lanza_claude(monkeypatch, cuota):
    cuota(Uso(90, True))
    llamado = []
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: llamado.append(1))
    codigo, motivo = ejecutar("web", "hola", explicito=True)
    assert codigo == 20 and "80" in motivo and llamado == []


def test_timeout_cuenta_la_llamada(monkeypatch, cuota):
    def lento(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    monkeypatch.setattr(claude_tope.subprocess, "run", lento)
    assert ejecutar("web", "hola", explicito=False)[0] == 21
    assert llamadas_hoy(date.today()) == 1


def test_claude_no_instalado_no_cuenta(monkeypatch, cuota):
    def falta(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(claude_tope.subprocess, "run", falta)
    assert ejecutar("web", "hola", explicito=False)[0] == 21
    assert llamadas_hoy(date.today()) == 0


def test_respuesta_ok(monkeypatch, cuota):
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"result": "ok", "is_error": False}), stderr=""))
    assert ejecutar("web", "hola", explicito=False) == (0, "ok")
    assert llamadas_hoy(date.today()) == 1


def test_respuesta_con_error_de_claude(monkeypatch, cuota):
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=1, stdout=json.dumps({"result": "Not logged in", "is_error": True}), stderr=""))
    codigo, texto = ejecutar("web", "hola", explicito=False)
    assert codigo == 21 and "Not logged in" in texto


def test_perfil_desconocido(cuota):
    codigo, motivo = ejecutar("nada", "hola", explicito=True)
    assert codigo == 20 and "web" in motivo


def test_prompt_va_por_stdin_y_no_en_argv(monkeypatch, cuota):
    visto = {}
    def run(cmd, **k):
        visto["cmd"], visto["input"] = cmd, k.get("input")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "ok"}), stderr="")
    monkeypatch.setattr(claude_tope.subprocess, "run", run)
    ejecutar("web", "--dangerously-skip-permissions hola", explicito=False)
    assert visto["input"] == "--dangerously-skip-permissions hola"
    assert not any("hola" in c for c in visto["cmd"])


def test_ningun_perfil_mezcla_lectura_local_y_red():
    from asistente.claude_tope import cargar_perfiles
    locales, red = {"Read", "Grep", "Glob"}, {"WebSearch", "WebFetch"}
    for nombre, perfil in cargar_perfiles().items():
        h = set(filter(None, perfil["allowedTools"].split(",")))
        assert not (h & locales and h & red), nombre


def test_perfil_sin_herramientas():
    cmd = construir_comando({"allowedTools": "", "max_turns": 1, "model": "sonnet"})
    i = cmd.index("--tools"); assert cmd[i + 1] == ""
    assert "--allowedTools" not in cmd

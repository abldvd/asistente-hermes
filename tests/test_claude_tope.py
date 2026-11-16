import json
import subprocess
from datetime import date
from types import SimpleNamespace

import pytest

from asistente import claude_tope
from asistente.claude_tope import construir_comando, ejecutar
from asistente.uso import Uso, llamadas_hoy

PERFIL = {"allowedTools": "Read,Grep,Glob,WebSearch,WebFetch", "max_turns": 8, "model": "sonnet"}


def test_comando_acotado_y_sin_saltarse_permisos():
    cmd = construir_comando(PERFIL, "hola")
    assert cmd[:3] == ["claude", "-p", "hola"]
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
    codigo, motivo = ejecutar("lectura", "hola", explicito=True)
    assert codigo == 20 and "80" in motivo and llamado == []


def test_timeout_cuenta_la_llamada(monkeypatch, cuota):
    def lento(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    monkeypatch.setattr(claude_tope.subprocess, "run", lento)
    assert ejecutar("lectura", "hola", explicito=False)[0] == 21
    assert llamadas_hoy(date.today()) == 1


def test_claude_no_instalado_no_cuenta(monkeypatch, cuota):
    def falta(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(claude_tope.subprocess, "run", falta)
    assert ejecutar("lectura", "hola", explicito=False)[0] == 21
    assert llamadas_hoy(date.today()) == 0


def test_respuesta_ok(monkeypatch, cuota):
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"result": "ok", "is_error": False}), stderr=""))
    assert ejecutar("lectura", "hola", explicito=False) == (0, "ok")
    assert llamadas_hoy(date.today()) == 1


def test_respuesta_con_error_de_claude(monkeypatch, cuota):
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=1, stdout=json.dumps({"result": "Not logged in", "is_error": True}), stderr=""))
    codigo, texto = ejecutar("lectura", "hola", explicito=False)
    assert codigo == 21 and "Not logged in" in texto


def test_perfil_desconocido(cuota):
    codigo, motivo = ejecutar("nada", "hola", explicito=True)
    assert codigo == 20 and "lectura" in motivo

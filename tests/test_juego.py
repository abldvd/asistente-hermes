import subprocess

import pytest
from types import SimpleNamespace

from asistente import juego
from asistente.juego import hay_juego, gpu_util

JUEGOS = ["Cyberpunk2077.exe"]


def test_proceso_de_juego_sin_distinguir_mayusculas():
    assert hay_juego(["explorer.exe", "CYBERPUNK2077.EXE"], JUEGOS, None, 70) is True


def test_gpu_ajena_alta_cuenta_como_juego():
    assert hay_juego(["explorer.exe"], JUEGOS, 90, 70) is True


def test_sin_gpu_ni_juegos():
    assert hay_juego(["explorer.exe"], JUEGOS, None, 70) is False


def _col(pid, eng):
    b = chr(92)
    return f'"{b}{b}PC{b}GPU Engine(pid_{pid}_luid_0x0_0x1_phys_0_eng_{eng}_engtype_3D){b}Utilization Percentage"'


CSV = ('"(PDH-CSV 4.0)",' + ",".join([_col(100, 0), _col(100, 1), _col(200, 0)]) + "\n"
       '"11/17/2026 11:13:45.197","30.5","20.0","87.4"\n')


def test_gpu_ajena_excluye_los_pids_de_ollama():
    assert juego.gpu_ajena_de_csv(CSV, {200}) == 50
    assert juego.gpu_ajena_de_csv(CSV, set()) == 100  # se recorta a 100


def test_gpu_ajena_csv_raro():
    assert juego.gpu_ajena_de_csv("basura", set()) is None


def test_gpu_para_juego_sin_modelo_cargado_usa_nvidia_smi(monkeypatch):
    monkeypatch.setattr(juego, "ollama_ocupado", lambda: False)
    monkeypatch.setattr(juego, "gpu_util", lambda: 90)
    monkeypatch.setattr(juego, "gpu_ajena", lambda: pytest.fail("no hace falta"))
    assert juego.gpu_para_juego() == 90


def test_gpu_para_juego_con_modelo_cargado_excluye_ollama(monkeypatch):
    monkeypatch.setattr(juego, "ollama_ocupado", lambda: True)
    monkeypatch.setattr(juego, "gpu_util", lambda: 95)
    monkeypatch.setattr(juego, "gpu_ajena", lambda: 12)
    assert juego.gpu_para_juego() == 12


def test_gpu_util_sin_nvidia_smi(monkeypatch):
    def falla(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(juego.subprocess, "run", falla)
    assert gpu_util() is None


def test_gpu_util_salida_rara(monkeypatch):
    monkeypatch.setattr(juego.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout="abc\n"))
    assert gpu_util() is None


def test_gpu_util_salida_normal(monkeypatch):
    monkeypatch.setattr(juego.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout="37\n"))
    assert gpu_util() == 37


def test_gpu_ajena_con_salida_ilegible(monkeypatch):
    monkeypatch.setattr(juego.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=None))
    monkeypatch.setattr(juego, "pids_ollama", lambda: set())
    assert juego.gpu_ajena() is None


def test_subprocesos_no_decodifican_con_la_pagina_de_codigos(monkeypatch):
    vistos = []
    def run(cmd, **kw):
        vistos.append(kw)
        return SimpleNamespace(returncode=0, stdout=b"")
    monkeypatch.setattr(juego.subprocess, "run", run)
    juego.procesos_activos(); juego.gpu_util()
    assert all(not kw.get("text") for kw in vistos)

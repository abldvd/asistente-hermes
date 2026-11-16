import subprocess
from types import SimpleNamespace

from asistente import juego
from asistente.juego import hay_juego, gpu_util

JUEGOS = ["Cyberpunk2077.exe"]


def test_proceso_de_juego_sin_distinguir_mayusculas():
    assert hay_juego(["explorer.exe", "CYBERPUNK2077.EXE"], JUEGOS, None, 70, False) is True


def test_gpu_alta_sin_ollama_cuenta_como_juego():
    assert hay_juego(["explorer.exe"], JUEGOS, 90, 70, ollama_activo=False) is True


def test_gpu_alta_por_ollama_no_cuenta():
    assert hay_juego(["explorer.exe"], JUEGOS, 90, 70, ollama_activo=True) is False


def test_sin_gpu_ni_juegos():
    assert hay_juego(["explorer.exe"], JUEGOS, None, 70, False) is False


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

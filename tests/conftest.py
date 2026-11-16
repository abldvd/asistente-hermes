import pytest


@pytest.fixture(autouse=True)
def estado_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_ESTADO", str(tmp_path))
    return tmp_path

import pytest


@pytest.fixture(autouse=True)
def estado_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_ESTADO", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def secretos_temporales(tmp_path, monkeypatch):
    # Ningún test toca secretos/ reales (tokens, vales.key)
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(tmp_path / "secretos" / "google"))

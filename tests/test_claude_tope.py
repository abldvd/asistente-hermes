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
    monkeypatch.setattr(claude_tope.shutil, "which", lambda _: None)
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: pytest.fail("no debe llamar"))
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


def test_la_llamada_se_cuenta_antes_de_lanzar_claude(monkeypatch, cuota):
    # si Hermes mata el proceso a mitad, la cuota gastada ya está contada
    vistos = []
    def run(*a, **k):
        vistos.append(llamadas_hoy(date.today()))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "ok"}), stderr="")
    monkeypatch.setattr(claude_tope.subprocess, "run", run)
    assert ejecutar("web", "hola", explicito=False) == (0, "ok")
    assert vistos == [1] and llamadas_hoy(date.today()) == 1


def test_si_no_se_puede_contar_no_se_llama(monkeypatch, cuota):
    def falla(_):
        raise PermissionError("bloqueado")
    monkeypatch.setattr(claude_tope, "registrar_llamada", falla)
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: pytest.fail("no debe llamar"))
    codigo, motivo = ejecutar("web", "hola", explicito=False)
    assert codigo == 21 and "contador" in motivo


def test_otro_oserror_da_error_legible(monkeypatch, cuota):
    def falla(*a, **k):
        raise OSError("acceso denegado")
    monkeypatch.setattr(claude_tope.subprocess, "run", falla)
    codigo, motivo = ejecutar("web", "hola", explicito=False)
    assert codigo == 21 and "acceso denegado" in motivo


def test_timeout_por_defecto_menor_que_el_de_la_terminal_de_hermes():
    import inspect
    assert inspect.signature(ejecutar).parameters["timeout_s"].default < 180


def test_prompt_file_fuera_de_claude_cwd_se_rechaza(tmp_path, monkeypatch, capsys):
    f = tmp_path / "secreto.txt"
    f.write_text("CLAVE=x", encoding="utf-8")
    monkeypatch.setattr(claude_tope, "ejecutar", lambda *a, **k: pytest.fail("no debe llamar"))
    assert claude_tope.main(["--perfil", "web", "--prompt-file", str(f)]) == 20
    assert "claude_cwd" in capsys.readouterr().out


def test_prompt_file_dentro_de_claude_cwd_vale(monkeypatch, capsys):
    from asistente.estado import estado_dir
    d = estado_dir() / "claude_cwd"
    d.mkdir(parents=True, exist_ok=True)
    (d / "p.txt").write_text("hola", encoding="utf-8")
    monkeypatch.setattr(claude_tope, "ejecutar", lambda perfil, prompt, explicito: (0, prompt))
    assert claude_tope.main(["--perfil", "web", "--prompt-file", str(d / "p.txt")]) == 0
    assert "hola" in capsys.readouterr().out


def test_prompt_con_un_secreto_se_rechaza(tmp_path, monkeypatch, cuota):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=sk-or-v1-abcdef123456\nVACIA=\nCORTA=abc\n", encoding="utf-8")
    monkeypatch.setattr(claude_tope, "ARCHIVOS_SECRETOS", [env])
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: pytest.fail("no debe llamar"))
    codigo, motivo = ejecutar("web", "mira esto: sk-or-v1-abcdef123456", explicito=True)
    assert codigo == 20 and "secreto" in motivo and "sk-or" not in motivo
    assert llamadas_hoy(date.today()) == 0


def test_valores_cortos_no_cuentan_como_secreto(tmp_path, monkeypatch, cuota):
    env = tmp_path / ".env"
    env.write_text("CORTA=abc\n", encoding="utf-8")
    monkeypatch.setattr(claude_tope, "ARCHIVOS_SECRETOS", [env, tmp_path / "no-existe.env"])
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"result": "ok"}), stderr=""))
    assert ejecutar("web", "abc", explicito=False) == (0, "ok")


def test_prompt_con_refresh_token_de_google_se_rechaza(tmp_path, monkeypatch, cuota):
    g = tmp_path / "google"
    g.mkdir()
    (g / "token_seria.json").write_text(json.dumps(
        {"token": "ya29.tokendeaccesolargo", "refresh_token": "1//refrescolargo123", "client_id": "x"}),
        encoding="utf-8")
    (g / "client_secret.json").write_text(json.dumps({"installed": {"client_secret": "GOCSPX-secreto99"}}),
                                          encoding="utf-8")
    monkeypatch.setattr(claude_tope, "ARCHIVOS_SECRETOS", [])
    monkeypatch.setattr(claude_tope, "DIRS_SECRETOS_JSON", [g])
    monkeypatch.setattr(claude_tope.subprocess, "run", lambda *a, **k: pytest.fail("no debe llamar"))
    for fuga in ("1//refrescolargo123", "ya29.tokendeaccesolargo", "GOCSPX-secreto99"):
        assert ejecutar("web", f"mira {fuga}", explicito=True)[0] == 20

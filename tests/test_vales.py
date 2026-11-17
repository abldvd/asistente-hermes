import time

import pytest

from asistente import vales


def test_emitir_y_consumir_una_sola_vez():
    vales.emitir("asistente.google.gmail", ["etiquetar", "--ids", "a", "--confirmado"])
    vales.activar_pendientes()
    assert vales.consumir("asistente.google.gmail", ["etiquetar", "--ids", "a", "--confirmado"]) is True
    assert vales.consumir("asistente.google.gmail", ["etiquetar", "--ids", "a", "--confirmado"]) is False


def test_vale_ligado_a_los_argumentos_exactos():
    vales.emitir("asistente.google.gmail", ["etiquetar", "--ids", "a", "--confirmado"])
    vales.activar_pendientes()
    assert vales.consumir("asistente.google.gmail", ["etiquetar", "--ids", "b", "--confirmado"]) is False
    assert vales.consumir("asistente.google.calendario", ["etiquetar", "--ids", "a", "--confirmado"]) is False


def test_vale_caduca(monkeypatch):
    vales.emitir("m", ["x"])
    vales.activar_pendientes()
    real = time.time
    monkeypatch.setattr(vales.time, "time", lambda: real() + vales.VIGENCIA_S + 1)
    assert vales.consumir("m", ["x"]) is False


def test_anular_todos():
    vales.emitir("m", ["a"])
    vales.emitir("m", ["b"])
    vales.anular_todos()
    assert not vales.consumir("m", ["a"]) and not vales.consumir("m", ["b"])


def test_argv_de_un_comando():
    cmd = r'E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.google.gmail buscar --consulta "from:x y" --confirmado'
    assert vales.argv_de(cmd) == ("asistente.google.gmail", ["buscar", "--consulta", "from:x y", "--confirmado"])


def test_cli_gmail_con_confirmado_sin_vale_se_niega(monkeypatch, capsys):
    from asistente.google import gmail
    llamadas = []
    monkeypatch.setattr(gmail, "servicio", lambda c, a: llamadas.append(1))
    argv = ["etiquetar", "--cuenta", "seria", "--ids", "a", "--quitar", "INBOX", "--confirmado"]
    assert gmail.main(argv) == 20 and llamadas == []
    assert "aprobación" in capsys.readouterr().out


def test_cli_gmail_con_vale_continua(monkeypatch):
    from asistente.google import gmail
    monkeypatch.setattr(gmail, "servicio", lambda c, a: object())
    monkeypatch.setattr(gmail, "etiquetar", lambda *a, **k: 1)
    argv = ["etiquetar", "--cuenta", "seria", "--ids", "a", "--quitar", "INBOX", "--confirmado"]
    vales.emitir("asistente.google.gmail", argv)
    vales.activar_pendientes()
    assert gmail.main(argv) == 0


def test_cli_calendario_y_sugerencias_exigen_vale(monkeypatch):
    from asistente import sugerencias
    from asistente.google import calendario
    monkeypatch.setattr(calendario, "servicio", lambda c, a: (_ for _ in ()).throw(AssertionError("no")))
    assert calendario.main(["borrar", "--cuenta", "seria", "--id", "x", "--confirmado"]) == 20
    monkeypatch.setattr(sugerencias, "confirmar", lambda n, ahora: (_ for _ in ()).throw(AssertionError("no")))
    assert sugerencias.main(["confirmar", "1"]) == 20


def test_hook_emite_vale_al_pedir_aprobacion():
    from asistente.hook_confirmacion import decidir
    cmd = r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.google.gmail etiquetar --cuenta seria --ids a --quitar INBOX --confirmado"
    assert decidir({"tool_name": "terminal", "tool_input": {"command": cmd}})["action"] == "approve"
    vales.activar_pendientes()
    assert vales.consumir("asistente.google.gmail",
                          ["etiquetar", "--cuenta", "seria", "--ids", "a", "--quitar", "INBOX", "--confirmado"])


def test_hook_de_respuesta_anula_si_se_rechaza(monkeypatch):
    import io
    import json
    from asistente import hook_aprobacion
    for eleccion, queda in [("deny", False), ("timeout", False), ("cancelled", False), ("once", True)]:
        vales.emitir("m", ["x"])
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": eleccion}})))
        assert hook_aprobacion.main() == 0
        assert vales.consumir("m", ["x"]) is queda
        vales.anular_todos()


@pytest.fixture(autouse=True)
def clave_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(tmp_path / "secretos" / "google"))


def test_vale_pendiente_no_vale_hasta_aprobar():
    vales.emitir("m", ["x"])
    vales.activar_pendientes()
    assert vales.consumir("m", ["x"]) is True
    vales.emitir("m", ["y"])
    assert vales.consumir("m", ["y"]) is False  # sin aprobación


def test_vale_falsificado_se_rechaza():
    import json
    ruta = vales._dir() / f"{vales._huella('m', ['x'])}.json"
    ruta.write_text(json.dumps({"expira": time.time() + 99, "activo": True, "mac": "00"}), encoding="utf-8")
    assert vales.consumir("m", ["x"]) is False


def test_hook_aprobacion_activa_si_se_aprueba_y_falla_cerrado(monkeypatch):
    import io
    import json
    from asistente import hook_aprobacion
    vales.emitir("m", ["x"])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once"}})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["x"]) is True
    vales.emitir("m", ["x"])
    monkeypatch.setattr(vales, "activar_pendientes", lambda: (_ for _ in ()).throw(OSError("x")))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once"}})))
    hook_aprobacion.main()
    monkeypatch.undo()
    monkeypatch.setenv("ASISTENTE_SECRETOS", str(vales._clave_ruta().parent))
    vales.activar_pendientes()
    assert vales.consumir("m", ["x"]) is False  # se anuló al fallar


def test_hook_bloquea_tocar_la_carpeta_de_vales():
    from asistente.hook_confirmacion import decidir
    for tool, args in [("write_file", {"path": r"E:\asistente-hermes\estado\vales\a.json", "content": "{}"}),
                       ("terminal", {"command": "dir estado" + chr(92) + "vales"})]:
        assert decidir({"tool_name": tool, "tool_input": args})["action"] == "block"

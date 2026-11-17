import time

import pytest

from asistente import vales

vales_activar_real = vales.activar


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
        vales.emitir("m", ["x"], regla="r1")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": eleccion, "pattern_key": "r1"}})))
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
    vales.emitir("m", ["x"], regla="r1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once", "pattern_key": "r1"}})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["x"]) is True
    vales.emitir("m", ["x"], regla="r1")
    monkeypatch.setattr(vales, "activar", lambda r: (_ for _ in ()).throw(OSError("x")))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once", "pattern_key": "r1"}})))
    hook_aprobacion.main()
    monkeypatch.setattr(vales, "activar", vales_activar_real)  # restaurar solo esto: el estado sigue aislado
    vales.activar_pendientes()
    assert vales.consumir("m", ["x"]) is False  # se anuló al fallar


def test_hook_bloquea_tocar_la_carpeta_de_vales():
    from asistente.hook_confirmacion import decidir
    for tool, args in [("write_file", {"path": r"E:\asistente-hermes\estado\vales\a.json", "content": "{}"}),
                       ("terminal", {"command": "dir estado" + chr(92) + "vales"})]:
        assert decidir({"tool_name": tool, "tool_input": args})["action"] == "block"


def test_aprobar_activa_solo_el_vale_de_esa_regla(monkeypatch):
    import io
    import json
    from asistente import hook_aprobacion
    vales.emitir("m", ["a"], regla="confirmado:aaa")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once", "pattern_key": "confirmado:bbb"}})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["a"]) is False  # otra regla: no se activa
    vales.emitir("m", ["a"], regla="confirmado:aaa")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"extra": {"choice": "once", "pattern_key": "confirmado:aaa", "pattern_keys": ["confirmado:aaa"]}})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["a"]) is True


def test_aprobar_sin_clave_no_activa_nada(monkeypatch):
    import io
    import json
    from asistente import hook_aprobacion
    vales.emitir("m", ["a"], regla="confirmado:aaa")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"extra": {"choice": "once"}})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["a"]) is False


def test_emitir_anula_los_otros_pendientes():
    vales.emitir("m", ["a"], regla="r1")
    vales.emitir("m", ["b"], regla="r2")
    assert vales.activar({"r1", "r2"}) == 1
    assert vales.consumir("m", ["b"]) is True and vales.consumir("m", ["a"]) is False


def test_consumo_atomico_solo_una_vez(monkeypatch):
    vales.emitir("m", ["a"], regla="r1")
    vales.activar({"r1"})
    resultados = [vales.consumir("m", ["a"]), vales.consumir("m", ["a"])]
    assert resultados == [True, False]
    assert not list(vales._dir().glob("*"))  # no quedan restos


@pytest.mark.parametrize("cmd", ["type estado" + chr(92) + "v*les" + chr(92) + "x", "dir E:/asistente-hermes/estado/*",
                                 "type secr?tos" + chr(92) + ".env", "dir .." + chr(92) + "estado" + chr(92) + "vales"])
def test_comodines_en_rutas_sensibles_se_bloquean(cmd):
    from asistente.hook_confirmacion import decidir
    assert decidir({"tool_name": "terminal", "tool_input": {"command": cmd}})["action"] == "block"


def test_hermes_antepone_plugin_rule(monkeypatch):
    import io
    import json
    from asistente import hook_aprobacion
    vales.emitir("m", ["a"], regla="confirmado:aaa")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"choice": "once", "pattern_key": "plugin_rule:confirmado:aaa", "pattern_keys": ["plugin_rule:confirmado:aaa"]})))
    hook_aprobacion.main()
    assert vales.consumir("m", ["a"]) is True


def test_vigencia_cubre_el_tiempo_de_espera_de_hermes():
    assert vales.VIGENCIA_S >= 360  # approvals.timeout de Hermes = 300 s


def test_rule_key_no_se_repite_para_el_mismo_comando():
    from asistente.hook_confirmacion import decidir
    cmd = r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.google.gmail etiquetar --cuenta seria --ids a --quitar INBOX --confirmado"
    a = decidir({"tool_name": "terminal", "tool_input": {"command": cmd}})["rule_key"]
    b = decidir({"tool_name": "terminal", "tool_input": {"command": cmd}})["rule_key"]
    assert a != b  # "session"/"always" no deben saltarse el post_approval_response


def test_workdir_no_rompe_la_confirmacion():
    from asistente.hook_confirmacion import decidir
    cmd = r"E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.google.gmail etiquetar --cuenta seria --ids a --quitar INBOX --confirmado"
    r = decidir({"tool_name": "terminal", "tool_input": {"command": cmd, "workdir": "E:\asistente-hermes", "notify": "x"}})
    assert r["action"] == "approve"
    assert decidir({"tool_name": "terminal", "tool_input": {"command": "dir", "workdir": "E:/asistente-hermes/secretos/"}})["action"] == "block"

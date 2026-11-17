import json
import time
from datetime import date

from asistente.uso import Uso, leer_uso, puede_usar_claude, llamadas_hoy, registrar_llamada


def _archivo(tmp_path, datos):
    p = tmp_path / "uso.json"
    p.write_text(json.dumps(datos) if not isinstance(datos, str) else datos, encoding="utf-8")
    return p


def test_leer_uso_fresco(tmp_path):
    ahora = time.time()
    assert leer_uso(_archivo(tmp_path, {"pct": 10, "t": ahora - 60}), ahora) == Uso(10, True)


def test_leer_uso_viejo_no_es_fresco(tmp_path):
    ahora = time.time()
    assert leer_uso(_archivo(tmp_path, {"pct": 10, "t": ahora - 6 * 3600}), ahora).fresco is False


def test_leer_uso_ausente_o_vacio(tmp_path):
    ahora = time.time()
    assert leer_uso(tmp_path / "no.json", ahora) == Uso(None, False)
    assert leer_uso(_archivo(tmp_path, {}), ahora) == Uso(None, False)
    assert leer_uso(_archivo(tmp_path, "{roto"), ahora) == Uso(None, False)


def test_por_encima_del_umbral_se_deniega_aunque_sea_explicito():
    ok, motivo = puede_usar_claude(Uso(85, True), explicito=True, llamadas_hoy=0, tope=10)
    assert ok is False and "80" in motivo


def test_dato_no_fresco_solo_permite_explicito():
    assert puede_usar_claude(Uso(None, False), explicito=False, llamadas_hoy=0, tope=10)[0] is False
    assert puede_usar_claude(Uso(None, False), explicito=True, llamadas_hoy=0, tope=10)[0] is True


def test_tope_diario_alcanzado():
    assert puede_usar_claude(Uso(10, True), False, llamadas_hoy=10, tope=10)[0] is False


def test_dentro_de_limites_permite():
    assert puede_usar_claude(Uso(10, True), False, llamadas_hoy=3, tope=10)[0] is True


def test_contador_por_dia():
    assert registrar_llamada(date(2026, 11, 16)) == 1
    assert registrar_llamada(date(2026, 11, 16)) == 2
    assert llamadas_hoy(date(2026, 11, 16)) == 2
    assert llamadas_hoy(date(2026, 11, 17)) == 0


def test_tras_el_reinicio_de_la_ventana_el_uso_vuelve_a_cero(tmp_path):
    ahora = time.time()
    u = leer_uso(_archivo(tmp_path, {"pct": 85, "t": ahora - 3600, "resets_at": ahora - 60}), ahora)
    assert u == Uso(0, True)


def test_antes_del_reinicio_se_respeta_el_pct(tmp_path):
    ahora = time.time()
    u = leer_uso(_archivo(tmp_path, {"pct": 85, "t": ahora - 60, "resets_at": ahora + 600}), ahora)
    assert u == Uso(85, True)


def test_marca_de_tiempo_futura_no_es_fresca(tmp_path):
    ahora = time.time()
    assert leer_uso(_archivo(tmp_path, {"pct": 10, "t": ahora + 3600}), ahora).fresco is False


def test_llamadas_hoy_con_json_que_no_es_dict(tmp_path):
    from asistente.estado import escribir_json
    escribir_json("claude_llamadas", [1, 2])
    assert llamadas_hoy(date.today()) == 0


def test_leer_uso_incluye_la_semana(tmp_path):
    ahora = time.time()
    u = leer_uso(_archivo(tmp_path, {"pct": 10, "t": ahora - 60, "semana": 91}), ahora)
    assert u.semana == 91


def test_semana_al_90_bloquea_incluso_si_es_explicito():
    ok, motivo = puede_usar_claude(Uso(10, True, semana=90), explicito=True, llamadas_hoy=0, tope=10)
    assert not ok and "semanal" in motivo and "90" in motivo


def test_semana_por_debajo_del_umbral_permite():
    assert puede_usar_claude(Uso(10, True, semana=89), explicito=False, llamadas_hoy=0, tope=10)[0]


def test_semana_alta_con_dato_desfasado_tambien_bloquea():
    assert not puede_usar_claude(Uso(None, False, semana=95), explicito=True, llamadas_hoy=0, tope=10)[0]


def test_umbral_semanal_configurable():
    assert puede_usar_claude(Uso(10, True, semana=92), explicito=False, llamadas_hoy=0, tope=10,
                             umbral_semana=95)[0]

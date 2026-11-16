from asistente import vigia


def test_con_juego_descarga_cada_modelo_cargado():
    descargados = []
    n = vigia.paso(juego=True, cargados=lambda: ["gemma4-64k", "otro"], descargar=descargados.append)
    assert n == 2 and descargados == ["gemma4-64k", "otro"]


def test_sin_juego_no_toca_nada():
    descargados = []
    assert vigia.paso(juego=False, cargados=lambda: ["gemma4-64k"], descargar=descargados.append) == 0
    assert descargados == []


def test_error_al_descargar_no_rompe_el_bucle():
    def falla(_):
        raise OSError("ollama caído")
    assert vigia.paso(juego=True, cargados=lambda: ["m"], descargar=falla) == 0

import base64
import json

import pytest

from asistente.google import gmail
from asistente.google.gmail import Denegado, borrador, buscar, etiquetar, etiquetas, leer

ETIQUETAS = [{"id": "INBOX", "name": "INBOX"}, {"id": "UNREAD", "name": "UNREAD"},
             {"id": "TRASH", "name": "TRASH"}, {"id": "SPAM", "name": "SPAM"},
             {"id": "Label_1", "name": "Empleo"}, {"id": "Label_2", "name": "Privado"}]


def _b64(texto):
    return base64.urlsafe_b64encode(texto.encode()).decode()


class _Llamada:
    def __init__(self, resultado):
        self._r = resultado

    def execute(self):
        return self._r


class FakeGmail:
    """Imita la cadena svc.users().messages().list(...).execute() y registra las llamadas."""

    def __init__(self, mensajes=None):
        self.mensajes = mensajes or {}
        self.llamadas = []

    def users(self):
        return self

    def labels(self):
        return _Recurso(self, "labels")

    def messages(self):
        return _Recurso(self, "messages")

    def drafts(self):
        return _Recurso(self, "drafts")


class _Recurso:
    def __init__(self, fake, nombre):
        self.f, self.n = fake, nombre

    def list(self, **kw):
        self.f.llamadas.append((self.n, "list", kw))
        if self.n == "labels":
            return _Llamada({"labels": ETIQUETAS})
        return _Llamada({"messages": [{"id": i} for i in self.f.mensajes]})

    def get(self, **kw):
        self.f.llamadas.append((self.n, "get", kw))
        return _Llamada(self.f.mensajes[kw["id"]])

    def modify(self, **kw):
        self.f.llamadas.append((self.n, "modify", kw))
        return _Llamada({})

    def create(self, **kw):
        self.f.llamadas.append((self.n, "create", kw))
        return _Llamada({"id": "d1"})


def _msg(id_, ms, cuerpo_plano=None, cuerpo_html=None):
    partes = []
    if cuerpo_plano is not None:
        partes.append({"mimeType": "text/plain", "body": {"data": _b64(cuerpo_plano)}})
    if cuerpo_html is not None:
        partes.append({"mimeType": "text/html", "body": {"data": _b64(cuerpo_html)}})
    return {"id": id_, "threadId": "t" + id_, "internalDate": str(ms), "snippet": "hola",
            "labelIds": ["INBOX", "Label_1"],
            "payload": {"mimeType": "multipart/alternative", "parts": partes,
                        "headers": [{"name": "From", "value": "Ana <ana@x.es>"},
                                    {"name": "Subject", "value": "Entrevista"}]}}


def test_no_hay_funcion_de_envio():
    for nombre in ("enviar", "send", "responder", "reply", "reenviar", "forward"):
        assert not hasattr(gmail, nombre)
    with pytest.raises(SystemExit):
        gmail.main(["send", "--cuenta", "seria"])


def test_etiquetas_por_nombre():
    assert etiquetas(FakeGmail())["Empleo"] == "Label_1"


def test_etiqueta_de_la_lista_blanca_sin_confirmar():
    svc = FakeGmail()
    assert etiquetar(svc, "seria", ["m1"], poner=["Empleo"], quitar=["UNREAD"], confirmado=False) == 1
    mod = [c for c in svc.llamadas if c[1] == "modify"][0][2]
    assert mod["body"] == {"addLabelIds": ["Label_1"], "removeLabelIds": ["UNREAD"]}


def test_etiqueta_fuera_de_lista_sin_confirmar_se_rechaza():
    svc = FakeGmail()
    with pytest.raises(Denegado):
        etiquetar(svc, "seria", ["m1"], poner=["Privado"], quitar=[], confirmado=False)
    assert not [c for c in svc.llamadas if c[1] == "modify"]


def test_archivar_exige_confirmado():
    svc = FakeGmail()
    with pytest.raises(Denegado):
        etiquetar(svc, "seria", ["m1"], poner=[], quitar=["INBOX"], confirmado=False)
    assert etiquetar(svc, "seria", ["m1"], poner=[], quitar=["INBOX"], confirmado=True) == 1


@pytest.mark.parametrize("etiqueta", ["TRASH", "SPAM"])
def test_papelera_y_spam_exigen_confirmado(etiqueta):
    with pytest.raises(Denegado):
        etiquetar(FakeGmail(), "seria", ["m1"], poner=[etiqueta], quitar=[], confirmado=False)


def test_etiqueta_inexistente_da_lista_valida():
    with pytest.raises(ValueError) as e:
        etiquetar(FakeGmail(), "seria", ["m1"], poner=["Nope"], quitar=[], confirmado=True)
    assert "Empleo" in str(e.value)


def test_borrador_exige_confirmado():
    svc = FakeGmail()
    with pytest.raises(Denegado):
        borrador(svc, "a@b.es", "Hola", "texto", confirmado=False)
    assert borrador(svc, "a@b.es", "Hola", "texto", confirmado=True) == "d1"


def test_buscar_formatea_fecha_en_canarias():
    julio = 1784109600000  # 2026-07-15T10:00:00Z
    svc = FakeGmail({"m1": _msg("m1", julio, "x")})
    r = buscar(svc, "newer_than:1d", 5)
    assert r[0]["fecha"] == "2026-07-15T11:00:00+01:00"
    assert (r[0]["de"], r[0]["asunto"], r[0]["etiquetas"]) == ("Ana <ana@x.es>", "Entrevista", ["INBOX", "Empleo"])


def test_leer_recorta_cuerpo_y_quita_html():
    svc = FakeGmail({"m1": _msg("m1", 0, cuerpo_html="<p>Hola <b>mundo</b></p><style>x{}</style>" + "a" * 50)})
    r = leer(svc, "m1", max_cuerpo=20)
    assert r["cuerpo"].startswith("Hola mundo") and len(r["cuerpo"]) <= 21


def test_leer_prefiere_texto_plano():
    svc = FakeGmail({"m1": _msg("m1", 0, cuerpo_plano="plano", cuerpo_html="<p>html</p>")})
    assert leer(svc, "m1", 100)["cuerpo"] == "plano"


def test_cli_denegado_da_codigo_20(monkeypatch, capsys):
    monkeypatch.setattr(gmail, "servicio", lambda c, a: FakeGmail())
    assert gmail.main(["etiquetar", "--cuenta", "seria", "--ids", "m1", "--quitar", "INBOX"]) == 20
    assert "confirm" in json.loads(capsys.readouterr().out)["error"]

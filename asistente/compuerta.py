"""Compuerta de tareas programadas.

Cada cron de Hermes se ejecuta cada 30 min dentro de una ventana y consulta esta compuerta,
que decide si la tarea corre ahora, espera (juego abierto o sin cuota de Claude), se salta
(pasado el retraso máximo) o ya se hizo hoy. Eso cubre también los días con el PC apagado
a la hora prevista.

Códigos de salida: 0 EJECUTAR, 10 ESPERAR, 11 SALTAR (avisar), 12 HECHO/YA_SALTADO (silencio).
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta

from asistente import juego, uso
from asistente.estado import cargar_config, escribir_json, leer_json

CODIGOS = {"EJECUTAR": 0, "ESPERAR": 10, "SALTAR": 11, "HECHO": 12, "YA_SALTADO": 12}


def _estado_de_hoy(estado: dict, hoy: date) -> dict:
    if estado.get("fecha") == hoy.isoformat():
        return dict(estado)
    return {"fecha": hoy.isoformat(), "primer_intento": None, "hecho": False, "saltado": False}


def decidir(tarea: str, ahora: datetime, juego: bool, cuota_ok: bool, estado: dict,
            retraso_max_h: float) -> tuple[str, dict]:
    est = _estado_de_hoy(estado, ahora.date())
    if est["hecho"]:
        return "HECHO", est
    if est["saltado"]:
        return "YA_SALTADO", est
    if juego or not cuota_ok:
        if est["primer_intento"] is None:
            est["primer_intento"] = ahora.isoformat()
        if ahora - datetime.fromisoformat(est["primer_intento"]) > timedelta(hours=retraso_max_h):
            est["saltado"] = True
            return "SALTAR", est
        return "ESPERAR", est
    return "EJECUTAR", est


def _hay_juego_ahora(cfg: dict) -> bool:
    return juego.hay_juego(juego.procesos_activos(), cfg["juegos"], juego.gpu_para_juego(),
                           cfg["umbral_gpu"])


def _cuota_ok(cfg: dict) -> tuple[bool, str]:
    u = uso.leer_uso(cfg["ruta_uso"], time.time(), cfg["frescura_uso_h"])
    return uso.puede_usar_claude(u, explicito=False, llamadas_hoy=uso.llamadas_hoy(date.today()),
                                 tope=cfg["tope_claude_diario"], umbral=cfg["umbral_uso"],
                                 umbral_semana=cfg.get("umbral_semana", 90))


def marcar_hecho(tarea: str, ahora: datetime | None = None) -> None:
    ahora = ahora or datetime.now()
    clave = f"compuerta_{tarea}"
    est = _estado_de_hoy(leer_json(clave, {}), ahora.date())
    est["hecho"] = True
    escribir_json(clave, est)


def consultar(tarea: str, requiere_claude: bool = False) -> tuple[str, str]:
    """Decide y guarda el estado. Devuelve (decisión, motivos legibles)."""
    cfg = cargar_config()
    clave = f"compuerta_{tarea}"
    ahora = datetime.now()
    est = _estado_de_hoy(leer_json(clave, {}), ahora.date())
    hay_juego = _hay_juego_ahora(cfg)
    cuota_ok, motivo_cuota = _cuota_ok(cfg) if requiere_claude else (True, "")
    decision, est = decidir(tarea, ahora, hay_juego, cuota_ok, est, cfg["retraso_max_h"])
    escribir_json(clave, est)
    motivos = []
    if hay_juego:
        motivos.append("juego abierto")
    if not cuota_ok:
        motivos.append(motivo_cuota)
    return decision, ", ".join(motivos) or "sin impedimentos"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="asistente.compuerta")
    p.add_argument("--tarea", required=True)
    p.add_argument("--requiere-claude", action="store_true")
    p.add_argument("--hecho", action="store_true", help="marca la tarea como hecha hoy")
    a = p.parse_args(argv)
    if a.hecho:
        marcar_hecho(a.tarea)
        print(f"DECISION: HECHO — {a.tarea} marcada como hecha hoy")
        return 0
    decision, motivos = consultar(a.tarea, a.requiere_claude)
    print(f"DECISION: {decision} — {motivos}")
    return CODIGOS[decision]

if __name__ == "__main__":
    sys.exit(main())

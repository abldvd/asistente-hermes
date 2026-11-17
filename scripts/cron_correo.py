"""Cron correo-diario en modo --no-agent (aplicar.ps1 lo copia a %LOCALAPPDATA%\hermes\scripts).

Su salida se entrega tal cual por Telegram; vacía = silencio. Ver asistente/correo_auto.py.
"""
import sys

sys.path.insert(0, "E:/asistente-hermes")
from asistente.correo_auto import main  # noqa: E402

sys.exit(main())

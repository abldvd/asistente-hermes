"""Script previo del cron correo-diario (aplicar.ps1 lo copia a %LOCALAPPDATA%\hermes\scripts)."""
import sys

sys.path.insert(0, r"E:\asistente-hermes")
from asistente.correo_diario import main  # noqa: E402

sys.exit(main(["precheck"]))

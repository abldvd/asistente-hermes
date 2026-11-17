"""Lanzador del hook pre_tool_call de confirmación humana (se ejecuta con el Python del venv)."""
import sys

sys.path.insert(0, r"E:\asistente-hermes")
from asistente.hook_confirmacion import main  # noqa: E402

sys.exit(main())

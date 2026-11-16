"""Lanzador del hook pre_tool_call de delegate_task (Hermes lo ejecuta con su propio Python)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asistente.tope_delegacion import main  # noqa: E402

sys.exit(main())

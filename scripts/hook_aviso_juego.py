"""Lanzador del hook pre_llm_call de aviso de juego (Hermes lo ejecuta con su propio Python)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asistente.aviso_juego import main  # noqa: E402

sys.exit(main())

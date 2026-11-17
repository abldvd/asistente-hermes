"""Lanzador del hook post_approval_response (anula vales si no se aprueba)."""
import sys

sys.path.insert(0, r"E:\asistente-hermes")
from asistente.hook_aprobacion import main  # noqa: E402

sys.exit(main())

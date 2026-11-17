"""Acceso a Google (Gmail y Calendar) con un token OAuth por cuenta."""
import warnings

# google.api_core avisa de que Python 3.10 dejará de recibir soporte; no debe ensuciar la salida
# que lee el agente (pendiente: migrar el venv a 3.11+).
warnings.filterwarnings("ignore", category=FutureWarning, module=r"google\.api_core")

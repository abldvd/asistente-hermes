# Asistente Hermes

Asistente personal local construido sobre [Hermes Agent](https://github.com/NousResearch/hermes-agent) para un único usuario en Windows 11. Usa un modelo de lenguaje local (Ollama) y recurre a Claude, con topes de uso, solo cuando hace falta.

Qué hace:

- Resume a diario el correo de dos cuentas de Gmail y pone etiquetas ya existentes. **No envía correo**: el código no tiene ninguna función de envío.
- Propone eventos de calendario a partir de los correos y solo los crea tras confirmación.
- Ejecuta tareas diarias (búsqueda de empleo, noticias) y responde por Telegram.
- No molesta mientras el usuario juega: retrasa tareas y libera la GPU.

Privacidad: el correo y el calendario se procesan solo en el ordenador del usuario. Ver [PRIVACY.md](PRIVACY.md).

## Estructura

- `asistente/`: módulos Python (compuerta de tareas, topes de Claude, detección de juegos, OpenRouter de reserva).
- `config/`: configuración, reglas del agente (`config/hermes/SOUL.md`) y ajustes de Hermes.
- `skills/`: skills propias de Hermes.
- `scripts/aplicar.ps1`: aplica la configuración del repositorio a Hermes.
- `docs/`: diseño y planes de implementación.
- `evaluacion/`: pruebas de los modelos candidatos.

Los secretos (`secretos/`) y el estado (`estado/`) no se versionan.

## Tests

```
.venv\Scripts\python -m pytest -q
```

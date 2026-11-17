# Notas de Hermes (diferencias con el plan y hallazgos)

- Versión instalada: Hermes Agent v0.23.1 (stable), commit 3b4215785882, 16-nov-2026. Instalador `install.ps1` revisado antes de ejecutar (SHA256 en descargas, solo PATH de usuario, sin admin).
- **HERMES_HOME en Windows = `%LOCALAPPDATA%\hermes`** (no `~/.hermes`): config.yaml, .env, SOUL.md, skills/, cron/.
- `config.yaml` por defecto tiene ~2.400 líneas: en vez de una plantilla completa, el repo guarda overrides en `config/hermes/ajustes.txt` y `scripts/aplicar.ps1` los aplica con `hermes config set`.
- `auth.adopt_external_logins` venía a `true`: Hermes tomaría prestado el login de Claude Code (refresh tokens de un solo uso → podría cerrar la sesión de Claude Code). Puesto a `false`.
- Modelos auxiliares (compresión, títulos, búsqueda de sesiones, web_extract): `provider: auto` + `model: ''` = modelo principal, **respetando la cadena de fallback**. Si se añade OpenRouter como fallback, el texto de correos podría acabar allí en un fallo del local → decidir en la fase 0.
- Telemetría: `shared_metrics` desactivado explícitamente.
- One-shot: `hermes chat -Q -q "..."`. Primera respuesta con qwen35-64k en frío: ~52 s.
- Ollama 0.40.16. `OLLAMA_KEEP_ALIVE=5m` como variable de usuario. qwen35-64k ocupa 7,6 GB, 100 % en GPU.
- Claude Code CLI: `--bare` exige API key (no OAuth), así que no sirve. `--tools <lista>` reduce el contexto de ~41K a ~5K tokens por llamada.

## DirectSDK y hooks (16-nov)
- Plugin: `hermes plugins install claude-subscription-directsdk` + `hermes plugins enable claude-subscription-directsdk-experimental`.
- Hooks de shell: `hooks.pre_tool_call` en config.yaml; el gateway no pide consentimiento → entrada en `%LOCALAPPDATA%\hermes\shell-hooks-allowlist.json` (lo hace `aplicar.ps1`). `hermes hooks list|test|doctor`.
- El subproceso del hook NO hereda variables de entorno arbitrarias (p. ej. `ASISTENTE_ESTADO`): usa siempre `estado\` del repo.
- `hermes config set` con JSON desde PowerShell 5.1: escapar `"` como `\"`; una sección existente (`hooks`) solo se cambia por clave con punto (`hooks.pre_tool_call`).
- Tokens por sesión: `hermes sessions export f.jsonl --session-id ID` (campos input/cache_write/cache_read/output_tokens).

## Pendientes de la revisión final del plan 1 (17-nov)
- os.replace WinError 5 when target open — retry + cleanup tmp (estado.py)
- --hecho after midnight marks the new day (compuerta) — fix in plan 3
- EJECUTAR leaves no "running" mark → duplicate runs on long tasks — fix in plan 3
- SALTAR notice lost when the wait passes the window end
- game hook timeout 20 s vs inner timeouts (now 8+8+3 s)
- watcher unloads a model the user forced with "!" → cold reload per turn
- confirm whether cron turns fire pre_llm_call (game hook could block them)
- aplicar.ps1 re-applies hooks/skills.disabled every run (YAML vs JSON compare)
- aplicar.ps1 saved without BOM → mojibake in PS 5.1 output
- aplicar.ps1 allowlist JSON without "approvals" property throws
- non-dict JSON state could break compuerta (llamadas_hoy fixed)
- Límite semanal de Claude no se vigila (solo el de 5 h).
- claude_tope: el filtro de secretos solo reconoce valores literales de los .env (≥ 8 caracteres); un secreto codificado (base64, troceado) pasaría. El agente sigue pudiendo leer secretos con sus propias herramientas.

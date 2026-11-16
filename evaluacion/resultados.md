# Fase 0 — resultados (16-nov-2026)

Criterio: ≥ 2/3 por prueba. p1 = resumen con enlaces, p2 = herramientas encadenadas, p3 = extracción de evento (correo simulado, solo local).
Nota: p2 pregunta por la "compuerta", palabra que solo aparece en el plan, no en el diseño; se puntúa como correcto describir la comprobación previa (juego/cuota → retrasar/saltar).

| Modelo | p1 | p2 | p3 | Tiempo típico | GPU a 64K |
|---|---|---|---|---|---|
| gemma4-64k (gemma4:12b) | 3/3 (incluye Claude Code, sin enlaces falsos) | 2/3 | 3/3 | 40-90 s | ~11,1/12,3 GB (nvidia-smi), cabe justo |
| qwen35-64k (qwen3.5 9B) | 1/3 (inventa contenido, omite Claude Code) | 1/3 | 2/3 (una con offset +01:00 erróneo) | 10-35 s | 7,6 GB, 100 % GPU |
| mellum-64k (Mellum 2.1) | 2/3 | 0/3 (tool calling roto en Hermes: errores recursivos) | 2/3 | 15-180 s | 8,2 GB, 100 % GPU |
| **OR nemotron-3.5-super-vl:free** | 3/3 (marca "sin enlace" en el changelog) | 3/3 (cita compuerta.py) | — | 20-100 s | — |
| **OR ernie-5.5-flash-preview:free** | 3/3 | 3/3 (decidir(), 4 h, ejecuciones perdidas) | — | 14-47 s | — |
| **OR flint-v1.0:free** | 3/3 | 3/3 | — | 40-520 s (muy variable) | — |
| OR particle-1:free | 3/3 | 1/1 (2 × 429) | — | 20-70 s | — |
| OR ling-3.2-flash:free | 2/2 (1 timeout 600 s) | 2/2 (1 × 429) | — | 60-600 s | — |
| OR nemotron-3-ultra:free | 0/3 (enlace del changelog mal puesto o inventado) | 3/3 (antes 1/3 sin créditos) | — | 20-50 s | — |
| OR dots-3-note-preview:free | 1/3 (inventa/mal atribuye enlace) | 2/3 (una la confunde con claude_tope) | — | 35-90 s | — |
| OR nemotron-3.5-lightning:free | 2/3 (una vuelca la lista en bruto) | 1/3 (una vacía, una errónea) | — | 20-100 s | — |
| OR north-mini-code:free | 1/3 (inventa enlace github) | 0/3 (inglés; confunde con gateway) | — | 10-30 s | — |
| OR nemotron-3-nano-omni-30b:free | 0/3 (solo lista titulares) | 0/3 (la confunde con el cron) | — | — | — |
| OR lfm-3-1.7b:free | 1/3 (enlaces alterados) | 0/3 (429) | — | 12-36 s | — |
| OR gemma-4-31b-it / gemma-4-26b-a4b-it:free | 0/3 (429 siempre) | 0/3 (429) | — | — | — |
| OR inkling-2-small:free | — (OpenRouter rechaza la clave para este modelo) | — | — | — | — |

Límites OpenRouter: sin créditos 50 peticiones/día; con ≥10 créditos comprados 1.000/día, 20/min (docs FAQ y limits). Cuenta del usuario: ya con créditos (`is_free_tier: false`), clave con tope de gasto 1 $.
Los modelos :free populares devuelven 429 a menudo (saturación del proveedor, no de la cuenta).

Tandas OpenRouter tras comprar créditos; p3 no se envía a OpenRouter (correo = privado).

## Decisión (propuesta, pendiente de confirmar)
- Principal: **gemma4-64k** local (único que pasa p3 con calidad; correo y calendario nunca salen del PC).
- OpenRouter: **sin fallback automático** (los auxiliares heredarían el texto de correos). Uso manual con `/model` para charla general y noticias: nemotron-3.5-super-vl:free, alternativa ernie-5.5-flash-preview:free.
- Claude: nivel 2 vía `asistente.claude_tope`.

## Prueba DirectSDK (plugin `claude-subscription-directsdk` 0.3.5, oficial Nous, @6313fad5)
- Lanza `claude -p` sin herramientas propias de Claude (`--tools ''`, `--max-turns 1`, `--permission-mode dontAsk`, `--setting-sources ''`); las herramientas las ejecuta Hermes. Usa el login de Claude Code (`claude.ai`), sin API key.
- Directo (`--provider claude-subscription-directsdk-experimental -m sonnet`, "di OK"): funciona, 56 s; 17,1K tokens de escritura en caché + 404 de entrada (≈0,07 $ a precio de lista, cargado a la suscripción).
- Delegación (padre gemma4-64k local, `delegation.provider` = DirectSDK, `delegation.model` = sonnet): funciona, 48 s. Hijo: 20,2K escritura caché + 13,4K lectura caché + 481 de salida. Uso 5 h: 7 % → 8 % (resolución de 1 %, incluye la sesión de Claude Code abierta).
- Tope: hook de shell `pre_tool_call` (matcher `^delegate_task$`, `fail_closed`) → `asistente/tope_delegacion.py`: misma regla que `claude_tope` (80 %, dato fresco, tope diario 10), cuenta una llamada por subtarea. Probado de punta a punta: con 10/10 el modelo recibe el bloqueo y lo comunica.
- Decisión: cumple los 3 criterios (funciona, medible, con tope) → **se queda como vía de subagentes**. `claude_tope` se mantiene para tareas con WebSearch/WebFetch de Claude, que DirectSDK no expone.

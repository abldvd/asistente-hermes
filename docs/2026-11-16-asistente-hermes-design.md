# Asistente personal local con Hermes Agent — diseño

Fecha: 2026-11-16 · Estado: borrador pendiente de aprobación

## Intención

El usuario quiere un asistente que viva en su PC (Windows 11, RTX 3060 12 GB) y que:

1. Ejecute cada día su Job Hunter existente (`E:\job-hunter`).
2. Le busque noticias sobre optimización de Claude Code, modelos de IA nuevos y temas afines, rastreando Reddit, GitHub y la web.
3. Lea, resuma y etiquete su Gmail a diario; el resto de cambios en el buzón, solo cuando se lo pida.
4. Escriba en su Google Calendar cuando se lo pida, y le sugiera eventos a partir de los correos.
5. Tenga una interfaz para hacerle preguntas.

**Por qué:** ahorrar tokens de su suscripción de Claude. Lo rutinario lo hace un modelo local; Claude solo entra cuando hace falta.

## Objetivos, no-objetivos, anti-objetivos

- **Objetivos:** todo orquestado por Hermes Agent (opción A, elegida por el usuario); arranque automático al iniciar sesión; modelo local por defecto; Claude vía la suscripción del usuario (no API) cuando el local no basta.
- **No-objetivos:** reescribir el Job Hunter; migrar la puntuación de ofertas de `claude -p` al modelo local (cambio aparte, posible después); responder correos automáticamente.
- **Anti-objetivos (fracaso aunque funcione):**
  - Que consuma más cuota de Claude que hoy.
  - Que borre, archive o envíe correo sin una orden explícita.
  - Que cree eventos en el calendario sin confirmación.
  - Que Claude se ejecute con permisos sin restricción (`--dangerously-skip-permissions` / `bypassPermissions`).
  - Que use una API de pago.

## Restricciones

- Hermes Agent en **Windows nativo** (soportado; instalador `install.ps1`, se instala en `%LOCALAPPDATA%\hermes\`).
- Hermes exige **≥ 64K tokens de contexto**. Ollama solo da 4.096 por defecto en < 24 GB de VRAM: hay que fijar `num_ctx` (Modelfile) u `OLLAMA_CONTEXT_LENGTH`. Con 12 GB, un modelo de ~9-12B a 64K va justo.
- Ollama ya instalado (`%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, modelos en `E:\ollama\models`). Candidatos: Mellum 2.1 12B-A2.5B (MoE), `qwen3.5` 9B, `gemma4:12b`.
- La cuota de Claude se comparte con las sesiones de Claude Code. Ya existe `~/.claude/uso-5h.json` con el % del límite de 5 h; la norma del usuario es parar al 80 %.
- No se puede usar el proveedor `anthropic` con API key (coste).

## Enfoques considerados

- **A. Hermes lo orquesta todo** (*elegido*). Job Hunter, noticias, correo y calendario son tareas programadas y skills de Hermes. Todo en un sitio y conversable. Riesgo: un modelo local de 9-12B encadena peor varias acciones; se mitiga con Claude como subagente y con tareas acotadas.
- **B. Recolectores fijos en Python y Hermes solo como interfaz.** Más robusto y barato, pero el usuario prefiere un único agente.
- **C. Extender el Job Hunter con Claude Code headless.** Descartado: gasta cuota de Claude en todo.

## Diseño

### Componentes

| Pieza | Implementación |
|---|---|
| Núcleo | Hermes Agent, proveedor `custom` → Ollama `http://127.0.0.1:11434/v1`, modelo elegido en la fase 0 |
| Arranque | `hermes gateway install` → tarea programada `Hermes_Gateway` al iniciar sesión (el cron de Hermes corre dentro del gateway) |
| Interfaz | Telegram por el gateway (preguntas desde el móvil o el PC), más CLI/escritorio en el PC (*decisión mía, ver Preguntas*) |
| Correo y calendario | Skill oficial `google-workspace` (OAuth "Desktop app" en un proyecto propio de Google Cloud; solo APIs de Gmail y Calendar) |
| Claude | Skill empaquetada `claude-code` (`claude -p` sobre la suscripción OAuth ya iniciada), llamada desde un **wrapper con tope** |
| Job Hunter | Tarea cron de Hermes que ejecuta el script actual y resume el resultado |
| Noticias | Tarea cron de Hermes, con fuentes y temas configurables |

### Claude como subagente (nivel 2)

- Hermes llama a Claude con la skill `claude-code`, siempre a través de un wrapper (`claude-tope.ps1` o `.py`) que:
  1. Lee `~/.claude/uso-5h.json`: si es ≥ 80 %, se niega y lo dice.
  2. Lleva un contador diario de llamadas (tope por defecto: 10 al día, configurable) en `E:\asistente-hermes\estado\`.
  3. Ejecuta `claude -p` con `--allowedTools` restringido por tipo de tarea, `--max-turns` acotado y `--output-format json`. Nunca con `bypassPermissions`.
- **Cuándo escala:** cuando el usuario lo pide ("pregúntale a Claude"), y en tareas marcadas como difíciles (síntesis del informe de noticias si el local falla, clasificar correos ambiguos). El modelo local no escala por su cuenta más allá del tope.
- **Prueba del plugin `claude-subscription-directsdk` (petición del usuario).** En la fase 0 se instala (`hermes plugins install claude-subscription-directsdk`) y se prueba como `delegation.provider` (subagentes nativos de Hermes sobre Claude, modelo `sonnet`).
  - **Criterios de éxito:** funciona con el plan del usuario (la documentación de Hermes se contradice sobre Pro); el consumo por subagente es medible en `uso-5h.json`; se puede aplicar el mismo tope (≥ 80 % → no delegar; máximo de delegaciones al día), ya sea con un hook o plugin de Hermes o con un script previo que cambie `delegation.provider` a local al llegar al tope.
  - **Si cumple:** pasa a ser la vía principal para usar Claude, y la skill `claude-code` + wrapper queda como reserva.
  - **Si no cumple** (no funciona con el plan, o el tope no se puede aplicar): se desinstala, y los subagentes nativos usan el modelo local mientras Claude va solo por la skill + wrapper.

### Tareas programadas

1. **Job Hunter, 08:00 diario.**
   - Ejecuta el pipeline actual de `E:\job-hunter` como script previo y manda por Telegram un resumen corto: nº de ofertas, las mejores con su puntuación y la ruta al `index.html`.
   - Hay que **desactivar la tarea de Windows "JobHunter"** para que no se ejecute dos veces.
   - El Job Hunter sigue usando `claude -p` internamente; eso no cambia en este proyecto.
2. **Noticias, 08:30 diario.**
   - Fuentes: Reddit (r/ClaudeAI, r/LocalLLaMA, r/MachineLearning, r/singularity) vía JSON/RSS públicos; GitHub (releases de `anthropics/claude-code` y repos en tendencia de IA); Hacker News (Algolia API); blogs de Anthropic, OpenAI, Google DeepMind, Nous y Hugging Face.
   - Temas: optimización de Claude Code (skills, hooks, MCP, ahorro de tokens), modelos nuevos (sobre todo locales que quepan en 12 GB), agentes.
   - Proceso: un script previo trae y deduplica (sin LLM); el modelo local filtra y resume en un informe de 5-10 puntos con enlaces, que se manda por Telegram y se guarda en `E:\asistente-hermes\noticias\AAAA-MM-DD.md`.
   - Las fuentes y los temas viven en un archivo de configuración editable.

### Correo

Política aclarada por el usuario: la lectura es automática; la modificación del buzón es bajo petición, salvo las etiquetas.

**Dos cuentas de Gmail: personal y «seria».**
- Una autorización OAuth por cuenta, con el mismo proyecto de Google Cloud y un token por cuenta. En la fase 2 se verifica si `google-workspace` admite varias cuentas; si no, se usan dos perfiles de credenciales o un MCP de Gmail multicuenta.
- El resumen diario va en un único mensaje con una sección por cuenta, la seria primero.
- Cada cuenta tiene su propio esquema de etiquetas; la sesión de primer ordenado cubre las dos.
- Los eventos sugeridos van al calendario de la cuenta de la que vino el correo.
- Todas las acciones bajo petición indican la cuenta. Si es ambigua, Hermes pregunta.

- **Automático (cron diario, solo con modelo local o Claude, nunca OpenRouter):**
  - Lee los correos nuevos desde la última ejecución.
  - Envía un resumen por Telegram: lo importante primero y el resto agrupado.
  - **Pone etiquetas automáticamente** según el esquema que defina la sesión de primer ordenado. Hasta que exista ese esquema, no etiqueta.
  - Propone eventos (sección siguiente).
  - Guarda en `estado/` el último ID o fecha procesado para no repetir correos.
- **Bajo petición:** buscar y resumir a demanda; marcar como leído. Archivar, mover a spam o borrar requiere mostrar la lista y esperar confirmación.
- **Nunca** envía correo. Los borradores solo se crean si se piden explícitamente.

### Sugerencias de eventos desde el correo (automático)

- En la misma pasada diaria, el modelo detecta citas, entrevistas, plazos y eventos en los correos nuevos y comprueba en el calendario si ya existen.
- Por Telegram envía una lista corta («📅 Entrevista con X, jue 10:00 — ¿añadir?»), con botones o respuesta por número.
- Solo crea el evento si el usuario confirma.
- Las sugerencias pendientes se guardan en `estado/` para poder confirmarlas más tarde.

### Calendario

- Crea, mueve y borra eventos siempre tras mostrar un resumen (título, fecha y hora en zona `Atlantic/Canary`) y recibir confirmación. Las fechas siempre llevan zona horaria, porque la skill trata las fechas sin zona como UTC.

### Memoria

- `USER.md` de Hermes: perfil breve (profesión y ciudad del usuario, temas de interés, zona horaria). Los límites son pequeños (~500 y ~800 tokens), así que solo se guardan datos estables.

## Extensibilidad (requisito del usuario)

El usuario irá añadiendo funciones nuevas. La primera prevista es controlar y revisar un home server que va a montar.

- **Repo propio** `E:\asistente-hermes` (git) como fuente de verdad: `config/` (plantilla de `config.yaml` de Hermes, sin secretos), `skills/<modulo>/`, `scripts/<modulo>/`, `cron/` (definición de tareas como código), `docs/`. Un script `aplicar.ps1` sincroniza el repo con `~/.hermes` (enlaces o copia), de forma que añadir una función = añadir una carpeta + una entrada de cron/MCP, sin tocar las demás.
- **Un módulo por función** (job-hunter, noticias, correo, calendario, claude-tope). Cada módulo tiene sus skills, scripts, reglas de confirmación y un README de 5 líneas.
- **Integraciones nuevas vía MCP o skill**, no tocando el núcleo. Para el home server, la vía prevista es un MCP/skill de SSH con un usuario de solo lectura por defecto, y acciones de control con confirmación (la misma política que el correo). Si el servidor usa Home Assistant, Hermes ya trae un adaptador.
- **Secretos** fuera del repo (`secretos\.env`, ignorado por git), igual que en el Job Hunter.

## Plan por fases (resumen para el builder)

0. **Prueba del modelo local:** instalar Hermes, configurar Ollama a 64K y probar los 2-3 candidatos con 3 tareas reales (resumir noticias, buscar correo + etiquetar, crear un evento). Elegir según calidad antes que velocidad (preferencia del usuario).
1. Gateway, Telegram y arranque automático.
2. Google Workspace (OAuth) con las reglas de confirmación.
3. Wrapper de Claude con tope y skill `claude-code`.
4. Cron del Job Hunter y desactivación de la tarea de Windows.
5. Cron de noticias y script recolector.

## Lo que queda a criterio del builder

- Lenguaje del wrapper y del recolector (Python recomendado, igual que el Job Hunter).
- Formato exacto de los mensajes de Telegram.
- Cómo se expresan las reglas de confirmación (instrucciones en `SOUL.md`/skill, o `approval_mode` de Hermes).

## Decisiones tras la revisión (16-nov)

**Del usuario**
1. **Si ningún modelo local supera la fase 0** (64K de contexto en 12 GB): explorar los modelos gratuitos de OpenRouter (`:free`) como modelo principal o de reserva (`fallback_providers`). *Condición mía:* los modelos gratis pueden registrar los prompts y tienen límites diarios bajos (cifras exactas a verificar en la fase 0), así que el **correo y el calendario nunca salen hacia OpenRouter**. Esas tareas usan el modelo local o Claude; OpenRouter solo hace noticias y charla general. Esto se aplica con perfiles o con `auxiliary`/`delegation` por tarea, según lo que permita Hermes.
2. **GPU y juegos (importante):** `keep_alive` de Ollama en 5 min. Antes de cada tarea cron, un script previo comprueba si hay un juego abierto (lista de procesos configurable, más una GPU ocupada por encima de un umbral). Si lo hay, la tarea se retrasa en bloques de 30 min, hasta 4 h, y si no, se salta y se avisa. Los mensajes de Telegram mientras se juega reciben respuesta, pero con un aviso de que cargar el modelo puede afectar al juego. Si la carga falla por falta de VRAM, se informa y no se reintenta en bucle.
3. **Interfaz:** Telegram (bot privado restringido al ID de usuario del dueño) más CLI/escritorio en el PC.
4. **Correo:** lectura, resumen, etiquetado y sugerencias de eventos automáticos; el resto de cambios en el buzón, bajo petición. El esquema de etiquetas lo fija una sesión aparte de Claude Code que hará el primer ordenado del buzón; hasta entonces no se etiqueta. **Job Hunter:** si `uso-5h.json` es ≥ 80 % a la hora programada, se retrasa (bloques de 30 min, hasta 4 h).

**Mías (revisables)**
- **OAuth de Google:** la app se publica "en producción" sin verificar, para uso propio, y así el refresh token no caduca cada 7 días. Si no fuera posible, se vuelve a autorizar cada semana con un aviso por Telegram.
- **Ejecuciones perdidas:** el builder comprueba si el cron de Hermes las recupera. Si no, se mantiene un disparador de Windows al iniciar sesión que ejecuta `hermes cron run <tarea>` solo si ese día no se ha hecho.
- **`uso-5h.json` desfasado** (más de 5 h): el wrapper solo permite llamadas pedidas explícitamente por el usuario.

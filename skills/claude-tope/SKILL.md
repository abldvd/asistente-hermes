---
name: claude-tope
description: "Preguntar a Claude (suscripción del usuario) con tope de uso: petición explícita del usuario o tarea difícil que necesita búsqueda web."
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [Claude, Escalado, Cuota]
---

# Claude con tope

Única forma de llamar a Claude Code (`claude -p`) desde la terminal. El script comprueba la cuota (umbral 80 % del límite de 5 h y tope diario) antes de llamar. No llames a `claude` de ninguna otra manera.

## Cuándo usarla

- El usuario lo pide expresamente ("pregúntale a Claude…", "que lo mire Claude") → con `--explicito`.
- Tú decides que la tarea es difícil y necesita a Claude con búsqueda web → sin `--explicito`.
- Para razonamiento o código sin web, prefiere `delegate_task` (subagente en Claude, también con tope).

## Perfiles

- `web`: Claude puede usar WebSearch y WebFetch. Para investigar en internet.
- `analisis`: sin herramientas. Para razonar sobre un texto que tú le pases en el prompt.

Nunca pongas en el prompt correos, eventos ni datos personales salvo que el usuario lo pida.

## Cómo llamarla

1. Escribe el prompt completo en un archivo temporal UTF-8 (por ejemplo en `E:\asistente-hermes\estado\claude_cwd\prompt.txt`).
2. Ejecuta:

```
E:\asistente-hermes\.venv\Scripts\python.exe -m asistente.claude_tope --perfil web --prompt-file E:\asistente-hermes\estado\claude_cwd\prompt.txt [--explicito]
```

con el directorio de trabajo `E:\asistente-hermes` (o anteponiendo `cd /d E:\asistente-hermes &&`).

## Resultado

- Código 0: la salida es la respuesta de Claude. Resúmela o pásala al usuario.
- Código 20: denegado (cuota alta, tope diario o dato de uso desfasado). Dile al usuario el motivo que imprime el script. No reintentes.
- Código 21: error de Claude. Informa del error. No reintentes.

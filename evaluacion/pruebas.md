# Fase 0 — pruebas de modelos

Cada prueba se ejecuta 3 veces por modelo en una sesión nueva (`hermes chat -Q -q`). Aprobado: ≥ 2/3 en cada prueba y modelo 100 % en GPU a 64K.

1. **Resumen** (`p1`): resumir `material/items.md` en 5 puntos con enlaces. Aprueba si no inventa enlaces (todos están en el material) y cubre lo más relevante para un usuario interesado en Claude Code y modelos locales.
2. **Herramientas encadenadas** (`p2`): listar los .md de `E:\asistente-hermes\docs`, leer el diseño y explicar qué hace la compuerta. Aprueba si usa ≥ 2 herramientas y la explicación es correcta (retrasa tareas por juego o cuota, máx. 4 h, recupera ejecuciones perdidas).
3. **Extracción de evento** (`p3`): con "hoy" = lunes 16-nov-2026, el correo dice "el jueves que viene a las 10". Aprueba si devuelve JSON con inicio `2026-11-19T10:00:00+00:00` (o `2026-11-26` justificando "que viene" = semana próxima; ambas se aceptan si es coherente) y un fin posterior.

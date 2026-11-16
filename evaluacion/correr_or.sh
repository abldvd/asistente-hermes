#!/usr/bin/env bash
# Uso: bash correr.sh modelo1 [modelo2 ...]   — guarda salidas en resultados/<modelo>/<prueba>-<n>.txt
cd "$(dirname "$0")"
H="$LOCALAPPDATA/hermes/bin/hermes.exe"
P1="Resume en 5 puntos, en español, lo más relevante para alguien interesado en optimizar Claude Code y en modelos de IA locales. Usa SOLO la información de este material e incluye el enlace de cada punto tal cual aparece:
$(cat material/items.md)"
P2='Lista los archivos .md de E:\asistente-hermes\docs (y subcarpetas), lee el documento de diseño del asistente y explícame en 3-4 líneas qué hace la "compuerta" de tareas programadas.'
P3="$(cat p3.txt)"
for m in "$@"; do
  mkdir -p "resultados/${m//[/:]/_}"
  for n in 1 2 3; do
    for p in 1 2; do
      v="P$p"; ini=$(date +%s)
      timeout 600 "$H" chat -Q --provider openrouter -m "$m" -q "${!v}" > "resultados/${m//[/:]/_}/p$p-$n.txt" 2>&1
      echo "segundos=$(( $(date +%s) - ini ))" >> "resultados/${m//[/:]/_}/p$p-$n.txt"
      echo "$m p$p-$n listo"
    done
  done
  curl -s http://127.0.0.1:11434/api/ps > "resultados/${m//[/:]/_}/ps.json"
done

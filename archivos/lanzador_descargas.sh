#!/bin/bash
# Lanzador inteligente del organizador de descargas
# Se ejecuta al arrancar el Mac y cada día a las 9:00 AM
# Solo corre el script una vez por día

SCRIPT="/Users/santiagojimeneztellez/Projects/scripts/scripts-cotidianos/archivos/organizar_descargas.py"
MARCA_DIA="/tmp/organizar_descargas_ultima_vez.txt"
HOY=$(date +%Y-%m-%d)

# Si ya se ejecutó hoy, no hacer nada
if [ -f "$MARCA_DIA" ] && [ "$(cat $MARCA_DIA)" = "$HOY" ]; then
    exit 0
fi

# Ejecutar el organizador
/usr/bin/python3 "$SCRIPT"

# Guardar la fecha de hoy como "ya ejecutado"
echo "$HOY" > "$MARCA_DIA"

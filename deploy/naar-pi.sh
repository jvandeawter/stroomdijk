#!/bin/sh
# Zet de Stroomdijk-bestanden op de Pi in ~/stroomdijk en start (of vernieuwt) de containers.
# Raakt niets buiten ~/stroomdijk aan.
#
# Gebruik: deploy/naar-pi.sh [host]   (standaard admin@rpi.local)
set -eu
HOST="${1:-admin@rpi.local}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

ssh "$HOST" 'mkdir -p ~/stroomdijk/ha-config ~/stroomdijk/scripts ~/stroomdijk/geheim && chmod 700 ~/stroomdijk/geheim'
rsync -a "$HERE/deploy/compose.yaml" "$HOST:stroomdijk/compose.yaml"
rsync -a --delete "$HERE/scripts/" "$HOST:stroomdijk/scripts/"
# configuration.yaml mag de container zelf niet overschrijven; wij zijn de baas over dit ene bestand
rsync -a "$HERE/ha/configuration.yaml" "$HOST:stroomdijk/ha-config/configuration.yaml"

ssh "$HOST" 'cd ~/stroomdijk && docker compose up -d'

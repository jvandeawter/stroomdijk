#!/bin/sh
# Zet de Stroomdijk-bestanden op de Pi in ~/stroomdijk en start (of vernieuwt) de containers.
# Raakt niets buiten ~/stroomdijk aan.
#
# Gebruik: deploy/naar-pi.sh [host]   (standaard admin@rpi.local)
set -eu
HOST="${1:-admin@rpi.local}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SYNC="rsync -a --delete --exclude __pycache__ --exclude tests --exclude *.egg-info"

ssh "$HOST" 'mkdir -p ~/stroomdijk/ha-config ~/stroomdijk/scripts ~/stroomdijk/data ~/stroomdijk/app ~/stroomdijk/geheim && chmod 700 ~/stroomdijk/geheim'
rsync -a "$HERE/deploy/compose.yaml" "$HOST:stroomdijk/compose.yaml"
$SYNC "$HERE/scripts/" "$HOST:stroomdijk/scripts/"
$SYNC "$HERE/app/" "$HOST:stroomdijk/app/"
rsync -a "$HERE/deploy/Dockerfile.app" "$HOST:stroomdijk/app/Dockerfile"
# configuration.yaml mag de container zelf niet overschrijven; wij zijn de baas over dit ene bestand
rsync -a "$HERE/ha/configuration.yaml" "$HOST:stroomdijk/ha-config/configuration.yaml"

ssh "$HOST" 'cd ~/stroomdijk && docker compose up -d --build'

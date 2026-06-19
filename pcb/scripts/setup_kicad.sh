#!/usr/bin/env bash
# Instalacja KiCada (kicad-cli) w srodowisku - dla prawdziwego ERC/DRC, Gerberow,
# modelu 3D STEP i eksportu SVG. Idempotentny: pomija gdy juz jest.
#
# Uzycie:           bash pcb/scripts/setup_kicad.sh
# Hook web sesji:   dodaj wywolanie tego skryptu w .claude/hooks/session_start
#                   (uwaga: instalacja jest duza ~1.5GB - rozwaz opt-in).
set -e

if command -v kicad-cli >/dev/null 2>&1; then
    echo "kicad-cli juz zainstalowany: $(kicad-cli version)"
    exit 0
fi

echo "Instaluje KiCad..."
apt-get update -qq || true

# Preferuj KiCad 8 (ERC/DRC z CLI). Jesli PPA niedostepne, uzyj wersji z repo.
if command -v add-apt-repository >/dev/null 2>&1; then
    add-apt-repository -y ppa:kicad/kicad-8.0-releases 2>/dev/null || true
    apt-get update -qq || true
fi

apt-get install -y --no-install-recommends kicad || \
    apt-get install -y --no-install-recommends kicad-cli || {
        echo "Nie udalo sie zainstalowac KiCada (sprawdz polityke sieciowa srodowiska)."
        exit 1
    }

echo "Gotowe: $(kicad-cli version)"
echo "Uwaga: ERC/DRC z linii polecen wymaga KiCad >= 8."

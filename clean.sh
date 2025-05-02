#!/usr/bin/env bash

# Remove the downloaded audio file (default: extracted_audio.wav)
# Usage: ./clean.sh [filename]

# Default
FILE=${1:-extracted_audio.wav}

if [[ -f "$FILE" ]]; then
    rm -v "$FILE"
    echo "Removed file: $FILE"
else
    echo "File not found: $FILE"
    exit 1
fi

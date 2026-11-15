#!/usr/bin/env bash
# Download the pinned load generator (bench/config.json) and verify its checksum.
# Usage: bench/install-bombardier.sh DIR   (prints the binary path)
set -euo pipefail
dir="${1:?target directory}"
cfg="$(dirname "$0")/config.json"
url="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["load_generator"]["url"])' "$cfg")"
sha="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["load_generator"]["sha256"])' "$cfg")"
mkdir -p "$dir"
curl --fail --silent --show-error --location --retry 3 -o "$dir/bombardier" "$url"
echo "$sha  $dir/bombardier" | sha256sum --check --quiet
chmod +x "$dir/bombardier"
echo "$dir/bombardier"

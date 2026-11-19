#!/usr/bin/env bash
# Install the load generator and print the binary path.
# - wrk (default): bench/config.json "load_generator". wrk publishes no
#   binaries: the pinned source tarball is checked by SHA-256 and built (needs
#   make, a C compiler, unzip and the OpenSSL headers; seconds on a runner).
# - oha: the documented fallback in bench/loadgens.json, a release binary
#   checked by SHA-256.
# Usage: bench/install-loadgen.sh DIR [wrk|oha]
set -euo pipefail
dir="${1:?target directory}"
tool="${2:-wrk}"
here="$(dirname "$0")"
case "$tool" in
  wrk) cfg="$here/config.json"; key=load_generator ;;
  oha) cfg="$here/loadgens.json"; key=oha ;;
  *) echo "unknown tool $tool (wrk or oha)" >&2; exit 2 ;;
esac
field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]].get(sys.argv[3], ""))' "$cfg" "$key" "$1"; }
mkdir -p "$dir"
if [ "$tool" = oha ]; then
  curl --fail --silent --show-error --location --retry 3 -o "$dir/oha" "$(field url)"
  echo "$(field sha256)  $dir/oha" | sha256sum --check --quiet
  chmod +x "$dir/oha"
  echo "$dir/oha"
  exit 0
fi
src="$dir/wrk-src"
rm -rf "$src" && mkdir -p "$src"
curl --fail --silent --show-error --location --retry 3 -o "$src.tar.gz" "$(field source_url)"
echo "$(field source_sha256)  $src.tar.gz" | sha256sum --check --quiet
tar -xzf "$src.tar.gz" -C "$src" --strip-components=1
make -C "$src" -j"$(nproc)" WITH_OPENSSL=/usr VER="$(field version)" >"$src.log" 2>&1 \
  || { tail -40 "$src.log" >&2; exit 1; }
cp "$src/wrk" "$dir/wrk"
echo "$dir/wrk"

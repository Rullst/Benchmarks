#!/usr/bin/env bash
# Install a phase-2 load generator candidate pinned in bench/loadgens.json and
# print the binary path. oha: the release binary, checked by SHA-256. wrk and
# wrk2 publish no binaries: the pinned source tarball is checked by SHA-256 and
# built (needs make, a C compiler, unzip and the OpenSSL headers).
# Usage: bench/install-loadgen.sh TOOL DIR   (TOOL: oha, wrk or wrk2)
set -euo pipefail
tool="${1:?tool: oha, wrk or wrk2}"
dir="${2:?target directory}"
cfg="$(dirname "$0")/loadgens.json"
field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]].get(sys.argv[3], ""))' "$cfg" "$tool" "$1"; }
mkdir -p "$dir"
case "$tool" in
  oha)
    curl --fail --silent --show-error --location --retry 3 -o "$dir/oha" "$(field url)"
    echo "$(field sha256)  $dir/oha" | sha256sum --check --quiet
    chmod +x "$dir/oha"
    echo "$dir/oha"
    ;;
  wrk|wrk2)
    src="$dir/$tool-src"
    rm -rf "$src" && mkdir -p "$src"
    curl --fail --silent --show-error --location --retry 3 -o "$src.tar.gz" "$(field source_url)"
    echo "$(field source_sha256)  $src.tar.gz" | sha256sum --check --quiet
    tar -xzf "$src.tar.gz" -C "$src" --strip-components=1
    if [ "$tool" = wrk ]; then
      make -C "$src" -j"$(nproc)" WITH_OPENSSL=/usr VER="$(field version)" >"$src.log" 2>&1 \
        || { tail -40 "$src.log" >&2; exit 1; }
    else
      make -C "$src" -j"$(nproc)" >"$src.log" 2>&1 || { tail -40 "$src.log" >&2; exit 1; }
    fi
    cp "$src/wrk" "$dir/$tool"
    echo "$dir/$tool"
    ;;
  *) echo "unknown tool $tool" >&2; exit 2 ;;
esac

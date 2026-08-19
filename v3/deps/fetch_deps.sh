#!/usr/bin/env bash
# Fetch pinned upstream dependencies for GridEval v3 into v3/deps/ (gitignored).
# These are NOT vendored into the repo (pin+reproduce, never vendor): NATIG
# alone is ~1GB of git history and the build images are ~489MB each.
#
# Usage:  bash v3/deps/fetch_deps.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NATIG_URL="https://github.com/pnnl/NATIG.git"
NATIG_COMMIT="e163b350e243c6386477e35dead979a4cb2b7c60"   # HEAD 2025-09-13

OPENDER_URL="https://github.com/epri-dev/OpenDER.git"
OPENDER_COMMIT="fe7877c664bc6c5eb3832499bf05e0f1dd1825c8" # release 2.2.0

clone_pinned () {  # url commit dest
  local url="$1" commit="$2" dest="$3"
  if [ -d "$dest/.git" ]; then
    echo "[=] $dest exists; fetching $commit"; git -C "$dest" fetch --depth 1 origin "$commit"
  else
    echo "[+] cloning $url -> $dest"; git clone "$url" "$dest"
  fi
  git -C "$dest" checkout -q "$commit"
  echo "[ok] $dest @ $(git -C "$dest" rev-parse --short HEAD)"
}

clone_pinned "$NATIG_URL"   "$NATIG_COMMIT"   "$HERE/natig-src"
clone_pinned "$OPENDER_URL" "$OPENDER_COMMIT" "$HERE/opender-src"

echo "[i] Create the OpenDER venv with:"
echo "    python3 -m venv $HERE/opender-venv && $HERE/opender-venv/bin/pip install -e $HERE/opender-src"

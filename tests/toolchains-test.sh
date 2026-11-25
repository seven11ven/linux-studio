#!/usr/bin/env bash
# End-to-end checks for the Toolchains explorer's sandboxed worker (Phase 4).
# Real downloads from nodejs.org and go.dev (~100 MB). Uses throwaway config/state folders.
#
# Usage: tests/toolchains-test.sh --runtime-dir <rootfs>
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$ROOT/src/launcher/linux-studio"
[[ "${1:-}" == --runtime-dir && -n "${2:-}" ]] || { echo "Usage: $0 --runtime-dir <rootfs>" >&2; exit 2; }
RUNTIME="$2"

T="$(mktemp -d)"
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT
export XDG_CONFIG_HOME="$T/config" XDG_DATA_HOME="$T/data"
unset DISPLAY WAYLAND_DISPLAY
"$LAUNCHER" --set-project-folder "$T/projects/project-folder" >/dev/null

PASS=0; FAIL=0
ok()   { echo "PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL  $1"; if [[ -n "${2:-}" ]]; then echo "      got: ${2//$'\n'/ | }"; fi; FAIL=$((FAIL+1)); }
worker() { printf '%s\n' "$@" | timeout 900 "$LAUNCHER" --runtime-dir "$RUNTIME" --toolchains-worker 2>&1 | grep -v '"progress"'; }
shell()  { "$LAUNCHER" --runtime-dir "$RUNTIME" --shell -c "$1" 2>&1; }

NODE_V="$(worker '{"op":"versions","tool":"node"}' | jq -r 'select(.op=="versions") | .items[] | select(.label|startswith("LTS")) | .version' | head -1)"
GO_V="$(worker '{"op":"versions","tool":"go"}' | jq -r 'select(.op=="versions") | .items[0].version')"
[[ "$NODE_V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$GO_V" =~ ^[0-9]+\.[0-9]+ ]] && ok "Version lists from nodejs.org and go.dev ($NODE_V, $GO_V)" || bad "Version lists" "$NODE_V $GO_V"

out="$(worker "{\"op\":\"install\",\"tool\":\"node\",\"version\":\"$NODE_V\"}" "{\"op\":\"install\",\"tool\":\"go\",\"version\":\"$GO_V\"}")"
[[ "$(grep -c '"op": "done"' <<<"$out")" == 2 ]] && ok "Node.js (checksum + signature) and Go (checksum) installed" || bad "Install Node.js and Go" "$out"

out="$(shell 'node --version')"
[[ "$out" != "v$NODE_V" ]] && ok "Bundled Node.js used until a version is chosen ($out)" || bad "Bundled Node.js used until chosen" "$out"

worker "{\"op\":\"use\",\"tool\":\"node\",\"version\":\"$NODE_V\"}" "{\"op\":\"use\",\"tool\":\"go\",\"version\":\"$GO_V\"}" >/dev/null
out="$(shell 'node --version; go version')"
[[ "$out" == "v$NODE_V"$'\n'"go version go$GO_V linux/amd64" ]] && ok "Editor sandbox uses the chosen versions" || bad "Chosen versions used" "$out"

out="$(shell 'go env GOTELEMETRY GOTOOLCHAIN')"
[[ "$out" == $'off\nlocal' ]] && ok "Go telemetry off, no automatic Go downloads" || bad "Go telemetry off" "$out"

out="$(shell 'touch /toolchains/x 2>&1; touch /toolchains/node/current/bin/x 2>&1')"
[[ "$(grep -c 'Read-only' <<<"$out")" == 2 ]] && ok "Toolchains are read-only inside the editor sandbox" || bad "Toolchains read-only" "$out"

out="$(worker "{\"op\":\"remove\",\"tool\":\"go\",\"version\":\"$GO_V\"}")"
if [[ ! -e "$XDG_DATA_HOME/linux-studio/toolchains/go/$GO_V" && ! -L "$XDG_DATA_HOME/linux-studio/toolchains/go/current" ]]; then ok "Remove deletes the version and its 'current' link"; else bad "Remove" "$out"; fi

out="$(worker '{"op":"install","tool":"node","version":"../../etc"}' '{"op":"install","tool":"evil","version":"1.0"}')"
[[ "$(grep -c '"op": "error"' <<<"$out")" == 2 ]] && ok "Odd tool or version names refused" || bad "Odd names refused" "$out"

# Security review #1: a compromised toolchain chosen with "Use this version" must never replace the worker's own
# tools. Plant fake gpgv / python3 / sh that leave a marker if run, then make the worker verify and list things.
TC="$XDG_DATA_HOME/linux-studio/toolchains"
mkdir -p "$TC/python/9.9.9/bin"
for tool in gpgv python3 sh gcc git; do
  printf '#!/bin/sh\ntouch /toolchains/python/9.9.9/PWNED-%s\necho "[GNUPG:] VALIDSIG FAKE"\nexit 0\n' "$tool" > "$TC/python/9.9.9/bin/$tool"
  chmod +x "$TC/python/9.9.9/bin/$tool"
done
ln -sfn 9.9.9 "$TC/python/current"
worker '{"op":"bundled"}' "{\"op\":\"install\",\"tool\":\"go\",\"version\":\"$GO_V\"}" >/dev/null
CMAKE_V="$(worker '{"op":"versions","tool":"cmake"}' | jq -r 'select(.op=="versions") | .items[0].version')"
out="$(worker "{\"op\":\"install\",\"tool\":\"cmake\",\"version\":\"$CMAKE_V\"}")"            # signed: runs gpgv
if grep -q '"op": "done"' <<<"$out"; then ok "Signed CMake $CMAKE_V installed with a planted fake gpgv present"; else bad "CMake install" "$out"; fi
if ! ls "$TC/python/9.9.9/" | grep -q PWNED; then ok "Worker never runs tools from installed toolchains"; else bad "Worker ran a planted tool" "$(ls "$TC/python/9.9.9/")"; fi
rm -rf "$TC/python"

# The worker's proxy only knows official sites.
S="$(mktemp -d)"
/usr/bin/python3 "$ROOT/src/network/studio_proxy.py" --socket "$S/p.sock" --fixed-allowlist "$ROOT/src/toolchains/official-sites.json" & P=$!
for _ in $(seq 30); do [[ -S "$S/p.sock" ]] && break; sleep 0.1; done
out="$(python3 - "$S/p.sock" <<'PY'
import socket, sys
for host in ["nodejs.org", "example.com", "api.anthropic.com"]:
    s = socket.socket(socket.AF_UNIX); s.connect(sys.argv[1])
    s.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
    print(host, s.recv(64).split(b"\r\n")[0].decode().split(" ")[1]); s.close()
PY
)"
kill "$P"; wait "$P" 2>/dev/null; rm -rf "$S"
[[ "$out" == $'nodejs.org 200\nexample.com 403\napi.anthropic.com 403' ]] && ok "Worker network: official sites only" || bad "Official sites only" "$out"

sleep 1
left_proc="$(pgrep -fc '^/usr/bin/python3 .*(studio_proxy|worker)\.py' || true)"
left_dir="$(find "${XDG_RUNTIME_DIR:-/tmp}" -maxdepth 1 -name 'linux-studio.*' | wc -l)"
left_stage="$(find "$XDG_DATA_HOME/linux-studio/toolchains/.staging" -mindepth 1 2>/dev/null | wc -l)"
[[ "$left_proc" == 0 && "$left_dir" == 0 && "$left_stage" == 0 ]] && ok "No worker, proxy, temp or staging files left" \
  || bad "Leftovers" "$left_proc processes, $left_dir temp folders, $left_stage staging files"

echo; echo "$PASS passed, $FAIL failed"
(( FAIL == 0 ))

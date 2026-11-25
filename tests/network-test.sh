#!/usr/bin/env bash
# End-to-end checks for Linux Studio's approved-websites proxy (Phase 3).
# Uses throwaway config/state folders and runs with no screen, so unknown sites are always denied.
# Needs internet access on the host (it contacts example.com and example.org).
#
# Usage: tests/network-test.sh --runtime-dir <rootfs>
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$ROOT/src/launcher/linux-studio"
[[ "${1:-}" == --runtime-dir && -n "${2:-}" ]] || { echo "Usage: $0 --runtime-dir <rootfs>" >&2; exit 2; }
RUNTIME="$2"

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export XDG_CONFIG_HOME="$T/config" XDG_DATA_HOME="$T/data"
unset DISPLAY WAYLAND_DISPLAY
"$LAUNCHER" --set-project-folder "$T/projects/project-folder" >/dev/null
NET="$XDG_CONFIG_HOME/linux-studio/network.json"
setnet() { printf '%s\n' "$1" > "$NET"; chmod 600 "$NET"; }

PASS=0; FAIL=0
run() { "$LAUNCHER" --runtime-dir "$RUNTIME" --shell -c "$1" 2>&1; }
check() {
  local out; out="$(run "$2")"
  if [[ "$out" =~ $3 ]]; then echo "PASS  $1"; ((PASS++)); else echo "FAIL  $1"; echo "      got: ${out//$'\n'/ | }"; ((FAIL++)); fi
}
code() { echo "curl -s -o /dev/null -m 15 -w '%{http_code}' $1 || true"; }
# Raw CONNECT through the bridge, printing the proxy's status line.
connect() { echo "exec 3<>/dev/tcp/127.0.0.1/3128; printf 'CONNECT $1 HTTP/1.1\r\nHost: $1\r\n\r\n' >&3; head -1 <&3 | tr -d '\r'"; }

setnet '{"network_enabled": true, "sites": {"example.com": {"status": "allowed", "last_used": ""}, "example.org": {"status": "blocked", "last_used": ""}, "127.0.0.1.nip.io": {"status": "allowed", "last_used": ""}}}'

check "Direct connection (bypassing proxy) fails"   "curl --noproxy '*' -s -m 5 https://example.com >/dev/null && echo ONLINE || echo OFFLINE" '^OFFLINE$'
check "No DNS inside the sandbox"                   'getent hosts example.com >/dev/null && echo RESOLVED || echo NONE' '^NONE$'
check "Approved site works through the proxy"       "$(code https://example.com)" '^200$'
check "Blocked site is refused"                     "$(code https://example.org)" '^000$'
check "Unknown site refused (no screen = deny)"     "$(code https://www.wikipedia.org)" '^000$'
check "Approval is exact: sub-address refused"      "$(code https://www.example.com)" '^000$'
check "Google spellchecker address pre-blocked"   "$(code https://redirector.gvt1.com)" '^000$'
check "Plain HTTP refused"                          "$(connect example.com:80)" '403'
check "SSH port refused"                            "$(connect example.com:22)" '403'
check "Loopback address refused"                    "$(connect 127.0.0.1:443)" '403'
check "Cloud metadata address refused"              "$(connect 169.254.169.254:443)" '403'
check "Private network address refused"             "$(connect 10.0.0.1:443)" '403'
check "localhost name refused"                      "$(connect localhost:443)" '403'
check "Approved name resolving to private IP refused" "$(connect 127.0.0.1.nip.io:443)" '403'
check "Non-CONNECT request refused"                 "exec 3<>/dev/tcp/127.0.0.1/3128; printf 'GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n' >&3; head -1 <&3 | tr -d '\r'" '405'
check "network.json is not visible inside"          "ls -A /home/user; cat '$NET' 2>&1 | head -1" 'No such file'
check "Terminal tools use the proxy"                'echo "$HTTPS_PROXY $http_proxy"' '^http://127.0.0.1:3128 http://127.0.0.1:3128$'

# Unknown site that was refused headless must NOT be saved as blocked.
if jq -e '.sites["www.wikipedia.org"] == null' "$NET" >/dev/null; then echo "PASS  Headless refusal is not saved"; ((PASS++)); else echo "FAIL  Headless refusal is not saved"; ((FAIL++)); fi
if jq -e '.sites["redirector.gvt1.com"] == null' "$NET" >/dev/null; then echo "PASS  Built-in block needs no saved entry"; ((PASS++)); else echo "FAIL  Built-in block needs no saved entry"; ((FAIL++)); fi
# "Last used" recorded for the approved site.
if jq -e '.sites["example.com"].last_used | length > 0' "$NET" >/dev/null; then echo "PASS  Last-used time recorded"; ((PASS++)); else echo "FAIL  Last-used time recorded"; ((FAIL++)); fi

setnet '{"network_enabled": false, "sites": {"example.com": {"status": "allowed", "last_used": ""}}}'
check "Network off refuses even approved sites"     "$(code https://example.com)" '^000$'

# Changes apply while running: turn the network on mid-session.
setnet '{"network_enabled": false, "sites": {"example.com": {"status": "allowed", "last_used": ""}}}'
out="$(run "$(code https://example.com); sleep 1; echo; while [ ! -e /tmp/go ]; do sleep 0.2; [ -e /project-folder/go ] && break; done; $(code https://example.com)" & sleep 3; jq '.network_enabled = true' "$NET" > "$NET.n" && mv "$NET.n" "$NET"; touch "$T/projects/project-folder/go"; wait)"
if [[ "$out" =~ ^000.*200$ ]]; then echo "PASS  Settings changes apply without restarting"; ((PASS++)); else echo "FAIL  Settings changes apply without restarting (got: ${out//$'\n'/ })"; ((FAIL++)); fi

# Nothing left behind after exit.
sleep 1
left_proc="$(pgrep -fc 'studio_proxy.py --socket' || true)"
left_dir="$(find "${XDG_RUNTIME_DIR:-/tmp}" -maxdepth 1 -name 'linux-studio.*' | wc -l)"
left_sock="$(ss -lx 2>/dev/null | grep -c 'linux-studio\.' || true)"
if [[ "$left_proc" == 0 && "$left_dir" == 0 && "$left_sock" == 0 ]]; then echo "PASS  No proxy process, socket or temp folder left"; ((PASS++))
else echo "FAIL  Left behind: $left_proc proxy, $left_sock sockets, $left_dir temp folders"; ((FAIL++)); fi

echo; echo "$PASS passed, $FAIL failed"
(( FAIL == 0 ))

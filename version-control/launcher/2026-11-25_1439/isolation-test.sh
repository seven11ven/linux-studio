#!/usr/bin/env bash
# Checks that Linux Studio's sandbox really is locked down (Phase 2: network fully off).
# Uses throwaway config/state folders, so your real Linux Studio settings are never touched.
#
# Usage: tests/isolation-test.sh --runtime-dir <rootfs>
# Exit code 0 = every check passed.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$ROOT/src/launcher/linux-studio"
[[ "${1:-}" == --runtime-dir && -n "${2:-}" ]] || { echo "Usage: $0 --runtime-dir <rootfs>" >&2; exit 2; }
RUNTIME="$2"

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export XDG_CONFIG_HOME="$T/config" XDG_DATA_HOME="$T/data"
PROJECT="$T/projects/project-folder"
"$LAUNCHER" --set-project-folder "$PROJECT" >/dev/null

PASS=0; FAIL=0
run() { "$LAUNCHER" --runtime-dir "$RUNTIME" --shell -c "$1" 2>&1; }
check() {  # check "<description>" "<command inside sandbox>" "<expected output regex>"
  local out; out="$(run "$2")"
  if [[ "$out" =~ $3 ]]; then echo "PASS  $1"; ((PASS++)); else echo "FAIL  $1"; echo "      got: ${out//$'\n'/ | }"; ((FAIL++)); fi
}

check "Only sandbox folders at /"            'ls / | tr "\n" " "'                     '^(app|bin|boot|dev|etc|home|lib|lib64|media|mnt|opt|proc|project-folder|root|run|sbin|srv|sys|tmp|usr|var| )+$'
check "Real home folder is not visible"      "ls /home; ls '$HOME' 2>&1 || true"     '^user'$'\n''.*No such file'
check "/etc/shadow is the runtime's, no passwords" "grep -cE '^[^:]+:\\\$' /etc/shadow; grep -c '^$(id -un):' /etc/shadow" '^0'$'\n''0$'
check "/sys is empty (no host kernel info)"   'ls -A /sys | wc -l'                    '^0$'
check "Hostname is studio"                   'hostname'                              '^studio$'
check "Username is user"                     'whoami'                                '^user$'
check "Only loopback network device"         'ip -o link | cut -d: -f2 | tr -d " "'  '^lo$'
check "No internet access"                   'curl -sS -m 5 https://example.com >/dev/null 2>&1 && echo ONLINE || echo OFFLINE' '^OFFLINE$'
check "Starts in /project-folder"            'pwd'                                   '^/project-folder$'
check "Prompt hides leading slash"           'cd /project-folder && mkdir -p apples && cd apples && . /etc/linux-studio/bashrc && __ls_path' '^project-folder/apples$'
check "No GPU device without --gpu"          'ls /dev/dri 2>&1 || true'              'No such file'
check "Editor folder empty in shell mode"    'ls -A /app | wc -l'                    '^0$'
check "Capabilities dropped"                 'grep CapEff /proc/self/status'         '0000000000000000'

# A file made inside appears in the chosen host folder, and nowhere else.
run 'echo hello > /project-folder/made-inside.txt' >/dev/null
if [[ "$(cat "$PROJECT/made-inside.txt" 2>/dev/null)" == hello ]]; then echo "PASS  File made inside appears in host project folder"; ((PASS++))
else echo "FAIL  File made inside appears in host project folder"; ((FAIL++)); fi

# machine-id changes every launch.
a="$(run 'cat /etc/machine-id')"; b="$(run 'cat /etc/machine-id')"
if [[ "$a" =~ ^[0-9a-f]{32}$ && "$a" != "$b" ]]; then echo "PASS  machine-id is random per launch"; ((PASS++))
else echo "FAIL  machine-id is random per launch ($a / $b)"; ((FAIL++)); fi

# Temporary identity files are cleaned up after exit.
left="$(find "${XDG_RUNTIME_DIR:-/tmp}" -maxdepth 1 -name 'linux-studio.*' 2>/dev/null | wc -l)"
if [[ "$left" == 0 ]]; then echo "PASS  No temporary identity files left behind"; ((PASS++))
else echo "FAIL  $left temporary identity folder(s) left behind"; ((FAIL++)); fi

# Unsafe project folders are refused.
bad=0; for p in / "$HOME" /etc /usr/share "$XDG_DATA_HOME/linux-studio/home"; do
  "$LAUNCHER" --validate-project-folder "$p" >/dev/null 2>&1 && { echo "      accepted unsafe folder: $p"; bad=1; }
done
if (( bad == 0 )); then echo "PASS  Unsafe project folders are refused"; ((PASS++)); else echo "FAIL  Unsafe project folders are refused"; ((FAIL++)); fi

echo; echo "$PASS passed, $FAIL failed"
(( FAIL == 0 ))

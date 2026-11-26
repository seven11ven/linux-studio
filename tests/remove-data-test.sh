#!/usr/bin/env bash
# Tests "Remove my Linux Studio data" and the extension-signature setting, using throwaway folders only.
# Usage: tests/remove-data-test.sh --runtime-dir <rootfs>
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; L="$ROOT/src/launcher/linux-studio"
[[ "${1:-}" == --runtime-dir && -n "${2:-}" ]] || { echo "Usage: $0 --runtime-dir <rootfs>" >&2; exit 2; }
R="$(realpath "$2")"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export XDG_CONFIG_HOME="$T/c" XDG_DATA_HOME="$T/d"
pass=0; fail=0; ok(){ echo "PASS  $1"; pass=$((pass+1)); }; bad(){ echo "FAIL  $1"; fail=$((fail+1)); }
"$L" --set-project-folder "$T/p/project-folder" >/dev/null; echo keep > "$T/p/project-folder/code.py"
mkdir -p "$T/d/linux-studio/home/.linux-studio/extensions/ext1" "$T/d/linux-studio/toolchains/node"
echo x > "$T/d/linux-studio/home/.linux-studio/extensions/ext1/a"
[[ "$("$L" --get-extension-signatures)" == check ]] && ok "Extension signatures are checked by default" || bad "default check"
"$L" --set-extension-signatures off >/dev/null && [[ "$("$L" --get-extension-signatures)" == off ]] && ok "Don't check is saved" || bad "set off"
"$L" --set-extension-signatures maybe >/dev/null 2>&1 && bad "bad value rejected" || ok "Unknown signature setting rejected"
[[ "$(grep -c PROJECT_FOLDER "$T/c/linux-studio/config")" == 1 ]] && ok "Other settings kept" || bad "other settings kept"
[[ "$("$L" --get-extension-size-limit)" == 512 ]] && ok "Largest extension to check defaults to 512 MB" || bad "size default"
"$L" --set-extension-size-limit 777 >/dev/null 2>&1 && bad "size value rejected" || ok "Unlisted size limit rejected"
"$L" --set-extension-size-limit 1024 >/dev/null
out="$("$L" --runtime-dir "$R" --shell -c 'cat /run/linux-studio/max-extension-mb; echo 64 > /run/linux-studio/max-extension-mb 2>/dev/null && echo WRITABLE' 2>/dev/null)"
[[ "$out" == 1024 ]] && ok "Size limit reaches the sandbox read-only (code inside can't change it)" || bad "size limit in sandbox (got: $out)"
"$L" --runtime-dir "$R" --shell -c 'sleep 6' >/dev/null 2>&1 & SP=$!; sleep 2
[[ "$("$L" --is-running)" == yes ]] && ok "A running Linux Studio is detected" || bad "detect running"
"$L" --remove-my-data-now extensions >/dev/null 2>&1 && bad "refuses while running" || ok "Removal refused while Linux Studio runs"
[[ -f "$T/d/linux-studio/home/.linux-studio/extensions/ext1/a" ]] && ok "Nothing removed while running" || bad "nothing removed while running"
wait "$SP"; [[ "$("$L" --is-running)" == no ]] && ok "Not running after exit" || bad "not running after exit"
"$L" --remove-my-data-now 'extensions;rm -rf /' >/dev/null 2>&1 && bad "bad parts rejected" || ok "Bad removal list rejected"
mkdir -p "$T/d/linux-studio/home/go/pkg/mod/example.com/lib@v1/sub"; echo x > "$T/d/linux-studio/home/go/pkg/mod/example.com/lib@v1/sub/f"
chmod 555 "$T/d/linux-studio/home/go/pkg/mod/example.com/lib@v1/sub" "$T/d/linux-studio/home/go/pkg/mod/example.com/lib@v1"
mkdir -p "$T/d/linux-studio/home/locked"; chmod 000 "$T/d/linux-studio/home/locked"
"$L" --remove-my-data-now extensions,toolchains >/dev/null && [[ ! -e "$T/d/linux-studio/home" && ! -e "$T/d/linux-studio/toolchains" ]] \
  && ok "Extensions and toolchains removed, including read-only (Go cache) and locked folders" || bad "removes"
[[ "$(cat "$T/p/project-folder/code.py")" == keep && -f "$T/c/linux-studio/config" ]] && ok "Project folder and settings untouched" || bad "untouched"
ln -s "$T/p/project-folder" "$T/d/linux-studio/home"
"$L" --remove-my-data-now extensions >/dev/null 2>&1 && bad "link refused" || ok "A folder replaced by a link is left alone"
[[ -f "$T/p/project-folder/code.py" ]] && ok "The link's target (project folder) is untouched" || bad "link target untouched"; rm "$T/d/linux-studio/home"
"$L" --remove-my-data-now settings >/dev/null && [[ ! -e "$T/c/linux-studio" ]] && ok "Settings removed when chosen" || bad "removes settings"
T2="$(mktemp -d)"; mkdir -p "$T2/x/linux-studio/home"
XDG_CONFIG_HOME="$T2/x" XDG_DATA_HOME="$T2/x" "$L" --remove-my-data-now settings >/dev/null 2>&1 && bad "overlap refused" || ok "Overlapping settings and data folders refused"
[[ -d "$T2/x/linux-studio/home" ]] && ok "Nothing removed when folders overlap" || bad "nothing removed on overlap"; rm -rf "$T2"
echo "" | "$L" --remove-my-data >/dev/null 2>&1 && bad "needs terminal" || ok "Interactive removal needs a terminal"
echo; echo "$pass passed, $fail failed"; (( fail == 0 ))

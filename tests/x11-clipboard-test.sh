#!/usr/bin/env bash
# Tests the private X11 display (Xephyr) and the clipboard bridge, without the editor.
# A fake desktop (Xvfb) plays your real screen; a small program on the private display plays an extension.
# Needs on the host: Xvfb, Xephyr, xdotool, bwrap, python3-xlib (system /usr/bin/python3).
#
# Usage: tests/x11-clipboard-test.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; mkdir -p "$T/x11" "$T/config"
PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT
PASS=0; FAIL=0
ok()  { echo "PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL  $1${2:+ (got: $2)}"; FAIL=$((FAIL+1)); }

H=97; N=7
Xvfb ":$H" -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 & PIDS+=($!)
for _ in $(seq 50); do [[ -S /tmp/.X11-unix/X$H ]] && break; sleep 0.1; done
# The private display, in its own sandbox (sees only the host display socket and its own socket folder).
bwrap --unshare-all --die-with-parent --new-session --ro-bind / / --tmpfs /home --tmpfs /tmp --tmpfs /run --proc /proc --dev /dev \
  --bind "$T/x11" /tmp/.X11-unix --ro-bind "/tmp/.X11-unix/X$H" "/tmp/.X11-unix/X$H" --setenv DISPLAY ":$H" \
  Xephyr ":$N" -title "Linux Studio" -resizeable -screen 1000x700 -nolisten tcp -nolisten local -no-host-grab \
    -extension XTEST -extension GLX -extension XVideo -extension MIT-SCREEN-SAVER -extension X-Resource \
  >/dev/null 2>&1 & PIDS+=($!)
for _ in $(seq 50); do [[ -S "$T/x11/X$N" ]] && break; sleep 0.1; done

setmode() { printf 'CLIPBOARD=%s\n' "$1" > "$T/config/config"; }
setmode paste-only
# The bridge, in its own sandbox: the two display sockets + read-only settings folder.
bwrap --unshare-all --die-with-parent --new-session --ro-bind / / --tmpfs /home --tmpfs /tmp --tmpfs /run --proc /proc --dev /dev \
  --bind "$T/x11" /tmp/.X11-unix --ro-bind "/tmp/.X11-unix/X$H" "/tmp/.X11-unix/X$H" --ro-bind "$T/config" /run/config \
  /usr/bin/python3 "$ROOT/src/display/clipboard_bridge.py" --host ":$H" --nested ":$N" --config-dir /run/config >"$T/bridge.log" 2>&1 & PIDS+=($!)
sleep 2

# Helpers: own a clipboard with text on a display / read it from a display. "inside" runs sandboxed like an extension.
cat > "$T/clip.py" <<'PY'
import sys, time
from Xlib import X, Xatom, display
from Xlib.protocol import event
mode, name = sys.argv[1], sys.argv[2]
d = display.Display(name); w = d.screen().root.create_window(0, 0, 1, 1, 0, d.screen().root_depth)
SEL = sys.argv[-1] if sys.argv[-1] in ("CLIPBOARD", "PRIMARY") else "CLIPBOARD"
CB, U8, TG = (Xatom.PRIMARY if SEL == "PRIMARY" else d.intern_atom("CLIPBOARD")), d.intern_atom("UTF8_STRING"), d.intern_atom("TARGETS")
if mode == "own":
    text = sys.argv[3].encode(); w.set_selection_owner(CB, X.CurrentTime); d.flush(); end = time.time() + float(sys.argv[4])
    while time.time() < end:
        while d.pending_events():
            e = d.next_event()
            if e.type == X.SelectionRequest:
                prop = e.property or e.target
                if e.target == TG: e.requestor.change_property(prop, Xatom.ATOM, 32, [TG, U8])
                else: e.requestor.change_property(prop, U8, 8, text)
                e.requestor.send_event(event.SelectionNotify(time=e.time, requestor=e.requestor, selection=e.selection, target=e.target, property=prop)); d.flush()
        time.sleep(0.02)
else:  # read
    P = d.intern_atom("T_DATA"); w.convert_selection(CB, U8, P, X.CurrentTime); d.flush(); end = time.time() + 1.5
    while time.time() < end:
        while d.pending_events():
            e = d.next_event()
            if e.type == X.SelectionNotify:
                if e.property == X.NONE: print("NONE"); sys.exit()
                r = w.get_full_property(P, X.AnyPropertyType); print(bytes(r.value).decode() if r else "NONE"); sys.exit()
        time.sleep(0.02)
    print("TIMEOUT")
PY
host()   { /usr/bin/python3 "$T/clip.py" "$@" 2>/dev/null; }
inside() { bwrap --unshare-all --die-with-parent --ro-bind / / --tmpfs /home --tmpfs /tmp --tmpfs /run --proc /proc --dev /dev \
             --bind "$T/x11" /tmp/.X11-unix --ro-bind "$T/clip.py" /run/clip.py /usr/bin/python3 /run/clip.py "$@" 2>/dev/null; }

# 0. Isolation
out="$(bwrap --unshare-all --ro-bind / / --tmpfs /tmp --proc /proc --dev /dev --ro-bind "$T/x11/X$N" "/tmp/.X11-unix/X$N" ls /tmp/.X11-unix)"
[[ "$out" == "X$N" ]] && ok "Inside sees only the private display socket" || bad "Only private socket visible" "$out"
out="$(inside read ":$N" 2>/dev/null; /usr/bin/python3 -c "from Xlib import display; d=display.Display(':$N'); print('XTEST' in d.list_extensions())" 2>/dev/null || bwrap --unshare-all --ro-bind / / --tmpfs /tmp --proc /proc --dev /dev --bind "$T/x11" /tmp/.X11-unix /usr/bin/python3 -c "from Xlib import display; d=display.Display(':$N'); print('XTEST' in d.list_extensions())")"
[[ "$out" == *False* ]] && ok "No fake-keyboard (XTEST) on the private display" || bad "XTEST disabled" "$out"

# 1. Paste only: background read gets nothing
host own ":$H" "SECRET-123" 20 & PIDS+=($!); sleep 1
out="$(inside read ":$N")"; [[ "$out" == NONE ]] && ok "Paste only: background read gets nothing" || bad "Background read blocked" "$out"
# 2. A real Ctrl+V typed into the Linux Studio window lets one paste through
W="$(DISPLAY=":$H" xdotool search --name '^Linux Studio$' | head -1)"
DISPLAY=":$H" xdotool windowactivate --sync "$W" >/dev/null 2>&1; DISPLAY=":$H" xdotool mousemove --window "$W" 200 200 click 1
DISPLAY=":$H" xdotool key --window "$W" ctrl+v; sleep 0.3
out="$(inside read ":$N")"; [[ "$out" == SECRET-123 ]] && ok "Paste only: a real Ctrl+V lets the paste through" || bad "Real paste works" "$out"
out="$(inside read ":$N")"; [[ "$out" == NONE ]] && ok "Paste only: one read per paste (a second read gets nothing)" || bad "One read per paste" "$out"
DISPLAY=":$H" xdotool key --window "$W" ctrl+v; sleep 1.5
out="$(inside read ":$N")"; [[ "$out" == NONE ]] && ok "Paste only: closed again after 1 second" || bad "Re-locks after 1 s" "$out"
# Desktop "selection" (highlighted text) is never shared in paste-only, even on a real middle-click
host own ":$H" "HIGHLIGHTED-PASSWORD" 6 PRIMARY & PIDS+=($!); sleep 1
DISPLAY=":$H" xdotool mousemove --window "$W" 300 300 click 2; sleep 0.3
out="$(inside read ":$N" PRIMARY)"; [[ "$out" != HIGHLIGHTED-PASSWORD ]] && ok "Paste only: desktop highlighted text never shared (middle-click)" || bad "Selection not shared" "$out"
# 3. Copy inside stays inside (paste only)
inside own ":$N" "INSIDE-TEXT" 4 & sleep 1
out="$(host read ":$H")"; [[ "$out" != INSIDE-TEXT ]] && ok "Paste only: text copied inside doesn't reach the desktop" || bad "Copy-out blocked" "$out"
sleep 3.5
# 4. Both directions
setmode both; sleep 1.5
host own ":$H" "HOST-BOTH" 6 & PIDS+=($!); sleep 1
out="$(inside read ":$N")"; [[ "$out" == HOST-BOTH ]] && ok "Both directions: desktop text readable inside" || bad "Both: host to inside" "$out"
inside own ":$N" "INSIDE-BOTH" 6 & sleep 1.5
out="$(host read ":$H")"; [[ "$out" == INSIDE-BOTH ]] && ok "Both directions: text copied inside reaches the desktop" || bad "Both: inside to host" "$out"
sleep 4.5
# 5. Switching back to paste-only takes effect without restarting
setmode paste-only; sleep 1.5
host own ":$H" "SECRET-AGAIN" 5 & PIDS+=($!); sleep 1
out="$(inside read ":$N")"; [[ "$out" == NONE ]] && ok "Switching back to Paste only applies immediately" || bad "Mode switch" "$out"

[[ -s "$T/bridge.log" ]] && { echo "bridge log:"; sed 's/^/  /' "$T/bridge.log" | tail -5; }
echo; echo "$PASS passed, $FAIL failed"
(( FAIL == 0 ))

#!/usr/bin/python3
"""Linux Studio clipboard bridge (X11 only). Connects your desktop's display with Linux Studio's private display
(Xephyr) and moves TEXT between their clipboards according to the Clipboard setting:

  paste-only (default): your desktop clipboard is handed to Linux Studio ONLY at the moment you really paste in its
      window with the keyboard (Ctrl+V, Ctrl+Shift+V or Shift+Insert): ONE read, within 1 second. "Really" means a
      real keypress from a real keyboard: the bridge watches XInput2 *raw* events on the private display, which
      programs can't fake (XTEST is disabled there, XSendEvent can't create them, and events from the virtual XTEST
      devices are ignored). The desktop's highlight-to-copy "selection" (middle-click) is NOT shared in this mode
      (PM decision, security review). Background reads get nothing; anything copied inside stays inside.
  both: copy and paste work both ways, like a normal app.

Runs on your real computer but in its own small sandbox that can only reach the two display sockets and read the
settings folder. Text only, capped at 1 MB. Standard library + python3-xlib.

Usage: clipboard_bridge.py --host :H --nested :N --config-dir DIR
"""
import argparse
import os
import select
import struct
import sys
import time

from Xlib import XK, X, Xatom, display, error
from Xlib.ext import ge, xfixes, xinput
from Xlib.protocol import event as xevent

MAX_TEXT = 1024 * 1024
ARM_SECONDS = 1.0             # one read allowed within this time after a real paste keypress
OWNER_FETCH_INTERVAL = 0.5    # "both" mode: at most one copy-out fetch per half second (DoS limit)
FETCH_TIMEOUT = 1.0
SELECTIONS = ("CLIPBOARD", "PRIMARY")


class Side:
    """One X display: a hidden window that can own selections, and helpers to read/serve text."""

    def __init__(self, name, label):
        self.d = display.Display(name)
        self.label = label
        screen = self.d.screen()
        self.win = screen.root.create_window(-10, -10, 1, 1, 0, screen.root_depth, event_mask=X.PropertyChangeMask)
        self.win.set_wm_name(f"Linux Studio clipboard bridge ({label})")
        self.atom = {n: self.d.intern_atom(n) for n in
                     ("CLIPBOARD", "PRIMARY", "TARGETS", "UTF8_STRING", "STRING", "TEXT", "text/plain;charset=utf-8",
                      "LS_BRIDGE_DATA", "ATOM")}
        self.atom["PRIMARY"] = Xatom.PRIMARY
        self.pending = []                           # events read while waiting for a conversion
        self.text = {s: None for s in SELECTIONS}   # what we serve when we own a selection on this side
        self.owned = {s: False for s in SELECTIONS}
        self.d.xfixes_query_version()   # XFIXES must be version-negotiated before use
        for s in SELECTIONS:
            self.d.xfixes_select_selection_input(self.win, self.atom[s], xfixes.XFixesSetSelectionOwnerNotifyMask)
        self.d.flush()

    def own(self, sel, text):
        self.text[sel] = text
        self.win.set_selection_owner(self.atom[sel], X.CurrentTime)
        self.d.flush()
        self.owned[sel] = self.d.get_selection_owner(self.atom[sel]) == self.win

    def fetch(self, sel):
        """Read the current text of a selection on this display (None if unavailable/too big)."""
        owner = self.d.get_selection_owner(self.atom[sel])
        if owner == X.NONE:
            return None
        if owner == self.win:
            return self.text[sel]
        prop = self.atom["LS_BRIDGE_DATA"]
        self.win.convert_selection(self.atom[sel], self.atom["UTF8_STRING"], prop, X.CurrentTime)
        self.d.flush()
        deadline = time.monotonic() + FETCH_TIMEOUT
        while time.monotonic() < deadline:
            while self.d.pending_events():
                ev = self.d.next_event()
                if ev.type == X.SelectionNotify and ev.requestor == self.win:
                    if ev.property == X.NONE:
                        return None
                    # Read at most MAX_TEXT bytes; anything larger is refused, never fully loaded (review #6).
                    r = self.win.get_property(prop, X.AnyPropertyType, 0, MAX_TEXT // 4 + 1)
                    self.win.delete_property(prop)
                    if (r is None or r.bytes_after > 0 or r.property_type == self.d.intern_atom("INCR")
                            or r.format != 8):
                        return None
                    data = r.value if isinstance(r.value, bytes) else bytes(r.value)
                    return data.decode("utf-8", "replace") if len(data) <= MAX_TEXT else None
                self.pending.append(ev)
            select.select([self.d], [], [], 0.05)
        return None

    def reply(self, req, text):
        """Answer a SelectionRequest with text (or refuse when text is None)."""
        prop = req.property if req.property != X.NONE else req.target
        ok = False
        if text is not None:
            if req.target == self.atom["TARGETS"]:
                targets = [self.atom[n] for n in ("TARGETS", "UTF8_STRING", "STRING", "TEXT", "text/plain;charset=utf-8")]
                req.requestor.change_property(prop, Xatom.ATOM, 32, targets)
                ok = True
            elif req.target in (self.atom["UTF8_STRING"], self.atom["TEXT"], self.atom["text/plain;charset=utf-8"]):
                req.requestor.change_property(prop, self.atom["UTF8_STRING"], 8, text.encode("utf-8"))
                ok = True
            elif req.target == self.atom["STRING"]:
                req.requestor.change_property(prop, Xatom.STRING, 8, text.encode("latin-1", "replace"))
                ok = True
        notify = xevent.SelectionNotify(time=req.time, requestor=req.requestor, selection=req.selection,
                                        target=req.target, property=prop if ok else X.NONE)
        req.requestor.send_event(notify)
        self.d.flush()


class Bridge:
    def __init__(self, host, nested, config_dir):
        self.host = Side(host, "desktop")
        self.nested = Side(nested, "Linux Studio")
        self.config = os.path.join(config_dir, "config")
        self.mode, self.mode_mtime = "paste-only", None
        self.armed_until = {s: 0.0 for s in SELECTIONS}
        self.ctrl, self.shift = set(), set()
        self.last_owner_fetch = 0.0
        d = self.nested.d
        self.kc = {name: d.keysym_to_keycode(XK.string_to_keysym(name))
                   for name in ("v", "Insert", "Control_L", "Control_R", "Shift_L", "Shift_R")}
        self.xi_major = d.query_extension(xinput.extname).major_opcode
        # Real input only: XInput2 raw keyboard events on the private display's root window, ignoring the
        # virtual "XTEST" devices (review #7).
        self.fake_devices = {dev.deviceid for dev in d.xinput_query_device(xinput.AllDevices).devices
                             if "XTEST" in dev.name}
        d.screen().root.xinput_select_events([(xinput.AllMasterDevices,
                                               xinput.RawKeyPressMask | xinput.RawKeyReleaseMask)])
        d.flush()
        self.read_mode()
        self.offer_host_text()
        self._ready = True

    # ---- settings ----
    def read_mode(self):
        try:
            mtime = os.stat(self.config).st_mtime_ns
        except FileNotFoundError:
            mtime = None
        if mtime == self.mode_mtime:
            return
        self.mode_mtime = mtime
        mode = "paste-only"
        try:
            with open(self.config, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("CLIPBOARD="):
                        mode = "both" if line.strip().split("=", 1)[1] == "both" else "paste-only"
        except OSError:
            pass
        changed = mode != self.mode
        self.mode = mode
        if changed and getattr(self, "_ready", False):
            self.offer_host_text()      # e.g. start/stop sharing the selection when switching modes

    # ---- desktop -> Linux Studio ----
    def shared(self):
        """Selections bridged in the current mode: paste-only shares only the clipboard, not the selection."""
        return SELECTIONS if self.mode == "both" else ("CLIPBOARD",)

    def offer_host_text(self):
        """Become the owner of the private display's shared selections so pastes come to us (fetched on demand)."""
        for s in self.shared():
            self.nested.own(s, None)

    # ---- events ----
    def on_raw(self, ev):
        evtype, data = ev.evtype, ev.data
        if not isinstance(data, (bytes, bytearray)) or len(data) < 10:
            return
        # XI2 raw event: deviceid(2) time(4) detail(4) sourceid(2)
        code = struct.unpack("=I", bytes(data[6:10]))[0]
        source = struct.unpack("=H", bytes(data[10:12]))[0] if len(data) >= 12 else None
        if source in self.fake_devices:
            return
        now = time.monotonic()
        if evtype == xinput.RawKeyPress:
            if code in (self.kc["Control_L"], self.kc["Control_R"]):
                self.ctrl.add(code)
            elif code in (self.kc["Shift_L"], self.kc["Shift_R"]):
                self.shift.add(code)
            elif code == self.kc["v"] and self.ctrl and self.held("Control_L", "Control_R"):
                self.armed_until["CLIPBOARD"] = now + ARM_SECONDS
            elif code == self.kc["Insert"] and self.shift and self.held("Shift_L", "Shift_R"):
                self.armed_until["CLIPBOARD"] = now + ARM_SECONDS
        elif evtype == xinput.RawKeyRelease:
            self.ctrl.discard(code)
            self.shift.discard(code)

    def held(self, *names):
        """Double-check with the server that the modifier is really down (no stuck Ctrl; review #8)."""
        keys = self.nested.d.query_keymap()
        return any(keys[self.kc[n] // 8] & (1 << (self.kc[n] % 8)) for n in names)

    def selection_name(self, side, atom):
        for s in SELECTIONS:
            if side.atom[s] == atom:
                return s
        return None

    def on_nested_request(self, ev):
        sel = self.selection_name(self.nested, ev.selection)
        text = None
        if sel in self.shared():
            if self.mode == "both":
                text = self.host.fetch(sel)
            elif time.monotonic() < self.armed_until[sel]:
                text = self.host.fetch(sel)
                if ev.target != self.nested.atom["TARGETS"]:
                    self.armed_until[sel] = 0.0      # one read per paste (PM decision); asking for formats is free
        self.nested.reply(ev, text)

    def on_host_request(self, ev):
        sel = self.selection_name(self.host, ev.selection)
        # We only own desktop selections in "both" mode, holding text copied inside Linux Studio.
        self.host.reply(ev, self.host.text.get(sel) if (sel and self.mode == "both") else None)

    def on_owner_change(self, side, ev):
        sel = self.selection_name(side, ev.selection)
        if not sel or ev.owner == side.win:
            return
        side.owned[sel] = False
        if sel not in self.shared():
            return
        if side is self.host:
            # New text copied on the desktop: make it available to Linux Studio again (still gated in paste-only).
            self.nested.own(sel, None)
        elif self.mode == "both":
            # Text copied inside Linux Studio: copy it out to the desktop (both directions only), rate-limited.
            now = time.monotonic()
            if now - self.last_owner_fetch < OWNER_FETCH_INTERVAL:
                return
            self.last_owner_fetch = now
            text = self.nested.fetch(sel)
            if text is not None:
                self.host.own(sel, text)

    def handle(self, side, ev):
        if getattr(ev, "send_event", 0):
            return   # ignore events forged by other programs with XSendEvent (review #9)
        if ev.type == X.SelectionRequest:
            if side is self.nested:
                self.on_nested_request(ev)
            else:
                self.on_host_request(ev)
        elif ev.type == X.SelectionClear:
            side.owned[self.selection_name(side, ev.atom) or "CLIPBOARD"] = False
        elif (ev.type, getattr(ev, "sub_code", None)) == side.d.extension_event.SetSelectionOwnerNotify:
            self.on_owner_change(side, ev)
        elif side is self.nested and ev.type == ge.GenericEventCode and getattr(ev, "extension", None) == self.xi_major:
            self.on_raw(ev)

    def safe_handle(self, side, ev):
        try:
            self.handle(side, ev)
        except (error.ConnectionClosedError, BrokenPipeError, ConnectionResetError):
            raise
        except Exception as e:  # noqa: BLE001 - one odd event must not stop the bridge
            print(f"linux-studio clipboard bridge: skipped an event ({type(e).__name__}: {e})", file=sys.stderr)

    def run(self):
        sides = {self.host.d.fileno(): self.host, self.nested.d.fileno(): self.nested}
        while True:
            self.read_mode()
            for side in sides.values():
                while side.pending:
                    self.safe_handle(side, side.pending.pop(0))
                while side.d.pending_events():
                    self.safe_handle(side, side.d.next_event())
            readable, _, _ = select.select(list(sides), [], [], 1.0)
            for fd in readable:
                side = sides[fd]
                while side.d.pending_events():
                    self.safe_handle(side, side.d.next_event())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--nested", required=True)
    ap.add_argument("--config-dir", required=True)
    args = ap.parse_args()
    try:
        bridge = Bridge(args.host, args.nested, args.config_dir)
    except Exception as e:  # noqa: BLE001 - report start-up problems plainly
        print(f"linux-studio clipboard bridge: could not start ({type(e).__name__}: {e}). Clipboard sharing is off.",
              file=sys.stderr)
        return 1
    try:
        bridge.run()
    except (error.ConnectionClosedError, BrokenPipeError, ConnectionResetError):
        return 0   # a display went away: Linux Studio is closing
    return 0


if __name__ == "__main__":
    sys.exit(main())

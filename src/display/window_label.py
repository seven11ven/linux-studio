#!/usr/bin/python3
"""Gives Linux Studio's private-display window its proper name and icon on your desktop.

Xephyr (the private display) introduces its window to your desktop as "Xephyr" with no icon, so your panel shows a
generic icon and can't link it to the Linux Studio menu entry. This short helper, started by the launcher right
after Xephyr, finds that window on your desktop and sets:
  * WM_CLASS     = linux-studio-editor (the StartupWMClass in the Linux Studio menu entry), and
  * _NET_WM_ICON = the LS icon (32, 64 and 128 px).
It only labels that one window, then exits (it gives up after 10 seconds). It runs in its own sandbox that sees only
your display socket and these files; it never touches the private display or anything inside Linux Studio.
Standard library + python3-xlib only.

Usage: window_label.py --host :0 --title "Linux Studio" --wm-class linux-studio-editor ICON.png [ICON.png ...]
"""
import argparse
import struct
import sys
import time
import zlib

from Xlib import X, Xatom, display, error

MAX_ICON = 256           # refuse oversized icon files (they are ours, but stay defensive)


def read_png_rgba(path):
    """Minimal PNG reader for our own icons: 8-bit RGBA, not interlaced. Returns (width, height, rows of RGBA bytes)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    if not ihdr:
        raise ValueError(f"{path}: no header")
    w, h, depth, ctype, _comp, _filt, interlace = ihdr
    if (depth, ctype, interlace) != (8, 6, 0) or not (0 < w <= MAX_ICON and 0 < h <= MAX_ICON):
        raise ValueError(f"{path}: must be 8-bit RGBA, not interlaced, at most {MAX_ICON}px")
    raw, stride, rows, prev = zlib.decompress(idat), w * 4, [], bytearray(w * 4)
    for y in range(h):
        ftype, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b = prev[i]
            c = prev[i - 4] if i >= 4 else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 255
            elif ftype == 2:
                line[i] = (line[i] + b) & 255
            elif ftype == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            elif ftype != 0:
                raise ValueError(f"{path}: bad PNG filter")
        rows.append(bytes(line))
        prev = line
    return w, h, rows


def net_wm_icon(paths):
    """_NET_WM_ICON data: for each size, width, height, then one 0xAARRGGBB number per pixel."""
    out = []
    for p in paths:
        w, h, rows = read_png_rgba(p)
        out += [w, h]
        for row in rows:
            for i in range(0, len(row), 4):
                r, g, b, a = row[i:i + 4]
                out.append((a << 24) | (r << 16) | (g << 8) | b)
    return out


def find_windows(d, title):
    """Top-level windows titled `title` whose class is still Xephyr's (i.e. not labelled yet)."""
    found, net_name, utf8 = [], d.intern_atom("_NET_WM_NAME"), d.intern_atom("UTF8_STRING")
    stack = [d.screen().root]
    while stack:
        w = stack.pop()
        try:
            children = w.query_tree().children
        except error.XError:
            continue
        for c in children:
            try:
                cls = c.get_wm_class()
                name = c.get_full_property(net_name, utf8)
                name = name.value.decode("utf-8", "replace") if name else (c.get_wm_name() or "")
            except error.XError:
                continue
            if cls and cls[1] == "Xephyr" and name == title:
                found.append(c)
            else:
                stack.append(c)   # window managers put app windows inside frame windows
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--wm-class", required=True)
    ap.add_argument("icons", nargs="+")
    args = ap.parse_args()
    icon = net_wm_icon(args.icons)
    d = display.Display(args.host)
    # The window can close while we label it (cosmetic helper): ignore X errors instead of printing them.
    d.set_error_handler(lambda *_a, **_k: None)
    deadline = time.time() + 10
    while time.time() < deadline:
        wins = find_windows(d, args.title)
        if wins:
            for w in wins:
                w.set_wm_class(args.wm_class, args.wm_class)
                w.change_property(d.intern_atom("_NET_WM_ICON"), Xatom.CARDINAL, 32, icon, X.PropModeReplace)
            d.flush()
            d.sync()
            return 0
        time.sleep(0.2)
    print("linux-studio: couldn't find the Linux Studio window to set its icon (cosmetic only)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # cosmetic helper: never let it disturb Linux Studio
        print(f"linux-studio: window icon helper failed (cosmetic only): {e}", file=sys.stderr)
        sys.exit(1)

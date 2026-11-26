"""Makes an important Linux Studio desktop window impossible to miss on X11 desktops.

On X11 a new small window can open behind a big one (for example the website approval pop-up behind the Linux Studio
window), and then nobody sees it. After the window appears, this asks the desktop's window manager, using the
standard EWMH messages every common desktop understands (Cinnamon, MATE, Xfce, KDE, GNOME on X11), to:
  * keep the window above other windows   (_NET_WM_STATE_ABOVE)
  * mark it as needing attention           (urgency hint, so its taskbar entry flashes)
It deliberately does NOT take keyboard focus (no _NET_ACTIVE_WINDOW): keys you are typing in the editor must never
land in an approval pop-up (security review 2026-11-26, finding 1).
It runs outside the sandbox, in the pop-up's own process. On Wayland, or if python3-xlib is missing, it quietly
does nothing (Wayland desktops decide window stacking themselves).
"""
import os


def demand_attention(gtk_window):
    if os.environ.get("WAYLAND_DISPLAY") or not os.environ.get("DISPLAY"):
        return
    try:
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        surface = gtk_window.get_surface()
        if not isinstance(surface, GdkX11.X11Surface):
            return
        xid = surface.get_xid()
        from Xlib import X, Xutil, display
        from Xlib.protocol import event
    except Exception:   # not X11, or python3-xlib missing: nothing to do
        return
    d = None
    try:
        d = display.Display()
        root = d.screen().root
        win = d.create_resource_object("window", xid)

        def ask(atom, data):
            ev = event.ClientMessage(window=win, client_type=d.intern_atom(atom), data=(32, data))
            root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)

        # 1 = add; source 1 = "from an application"
        ask("_NET_WM_STATE", [1, d.intern_atom("_NET_WM_STATE_ABOVE"), 0, 1, 0])
        hints = win.get_wm_hints() or {"flags": 0}
        try:
            flags = hints.flags
        except AttributeError:
            flags = hints.get("flags", 0)
        win.set_wm_hints(flags=flags | Xutil.UrgencyHint)
        d.flush()
    except Exception:
        pass   # cosmetic: the pop-up still works, it just might not be on top
    finally:
        if d is not None:
            d.close()

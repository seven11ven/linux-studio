"""Linux Studio window style for the GTK windows on your desktop (first-run, pop-up, websites, toolchains, settings).
Shared by every Linux Studio window. Colours come from the approved mockups
(project-notes/mockups/linux-studio-mockups.html). Follows the desktop's light/dark preference, like the editor does.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

APP_ICON = "io.github.seven11ven.linuxstudio"   # matches Icon= in the menu entry

PALETTES = {
    "dark": dict(bg="#0f1412", surface="#171e1b", panel="#1d2522", ink="#e3ebe7", muted="#97a59f", line="#2c3732",
                 accent="#4cc296", accent_hover="#5fd3a6", accent_ink="#06130e", accent_soft="#1c3a2f",
                 warn="#f0a950", warn_soft="#3a2b17", bad="#f2817a", bad_soft="#3b1e1c", term="#0a0e0d", term_ink="#cfe3da"),
    "light": dict(bg="#eef1f0", surface="#ffffff", panel="#f5f7f6", ink="#17201d", muted="#5b6762", line="#d5dcd9",
                  accent="#1f7a5c", accent_hover="#26946f", accent_ink="#ffffff", accent_soft="#dcefe7",
                  warn="#a35a00", warn_soft="#fbeedb", bad="#b3261e", bad_soft="#fbe3e1", term="#0f1513", term_ink="#cfe3da"),
}

CSS = """
window, window.background { background-color: {surface}; color: {ink}; }
label { color: {ink}; }
.ls-title { font-size: 1.35em; font-weight: 600; }
.ls-muted { color: {muted}; }
.ls-domain { font-family: monospace; font-size: 1.25em; font-weight: 600; }
.ls-note { background-color: {accent_soft}; border-radius: 4px; padding: 10px 12px; }
.ls-note-warn { background-color: {warn_soft}; border-radius: 4px; padding: 10px 12px; }
.ls-term { background-color: {term}; color: {term_ink}; font-family: monospace; border-radius: 4px; padding: 10px 12px; }
.ls-pill-warn { background-color: {warn_soft}; color: {warn}; border-radius: 7px; padding: 2px 10px; font-size: 0.85em; font-weight: 600; }
.ls-pill-ok { background-color: {accent_soft}; color: {accent}; border-radius: 7px; padding: 2px 10px; font-size: 0.85em; }
.ls-pill-bad { background-color: {bad_soft}; color: {bad}; border-radius: 7px; padding: 2px 10px; font-size: 0.85em; }
.ls-error { color: {bad}; }
entry { background-color: {panel}; color: {ink}; border: 1px solid {line}; border-radius: 4px; font-family: monospace; }
entry:focus-within { border-color: {accent}; box-shadow: 0 0 0 1px {accent}; outline: none; }
entry text selection, label selection { background-color: {accent_soft}; color: {ink}; }
button { background-image: none; background-color: {surface}; color: {ink}; border: 1px solid {line};
         border-radius: 4px; box-shadow: none; padding: 6px 14px; }
button:hover { background-color: {panel}; }
button.ls-primary { background-color: {accent}; color: {accent_ink}; border-color: {accent}; font-weight: 600; }
button.ls-primary label { color: {accent_ink}; }
button.ls-primary:hover { background-color: {accent_hover}; }
button.ls-danger, button.ls-danger label { color: {bad}; border-color: {bad}; }
button.ls-link { background-color: transparent; border-color: transparent; color: {muted}; padding: 2px 0; text-decoration: underline; }
button.ls-link label { color: {muted}; }
button.ls-link:hover label { color: {ink}; }
button.ls-link:hover { background-color: transparent; }
button:disabled { opacity: 0.5; }
button:focus-visible { outline: 2px solid {accent}; outline-offset: 2px; }
.ls-row { border-bottom: 1px solid {line}; padding: 6px 0; }
.ls-header { color: {muted}; font-size: 0.8em; font-weight: 600; }
headerbar { background-color: {panel}; color: {ink}; }
.ls-banner { background-color: {accent_soft}; color: {ink}; padding: 10px 16px; }
.ls-side { background-color: {panel}; border-right: 1px solid {line}; padding: 10px; min-width: 170px; }
button.ls-side-item { background-image: none; background-color: transparent; border-color: transparent; box-shadow: none; padding: 8px 10px; }
button.ls-side-item label { color: {ink}; font-weight: normal; }
button.ls-side-item:hover { background-color: {surface}; }
button.ls-side-item:checked { background-color: {accent_soft}; }
button.ls-side-item:checked label { color: {accent}; font-weight: 600; }
button.ls-choice:checked, button.ls-choice:checked label { background-color: {accent}; color: {accent_ink}; border-color: {accent}; font-weight: 600; }
.ls-subtitle { font-weight: 600; margin-top: 8px; }
.ls-mono { font-family: monospace; }
.ls-pill { background-color: {panel}; color: {muted}; border: 1px solid {line}; border-radius: 7px; padding: 2px 10px; font-size: 0.85em; }
"""


def css_for(scheme):
    css = CSS
    for key, value in PALETTES[scheme].items():
        css = css.replace("{" + key + "}", value)
    return css.encode()


def preferred_scheme():
    """'dark' or 'light', from the desktop's colour-scheme setting (the same one the editor follows).
    Asks the desktop portal first (GNOME, Cinnamon, KDE...), then GTK's own settings. Defaults to dark."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                              "org.freedesktop.portal.Settings", "Read",
                              GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                              GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 1000, None)
        value = reply.unpack()[0]
        while isinstance(value, GLib.Variant):
            value = value.unpack()
        if value == 1:
            return "dark"
        if value == 2:
            return "light"
    except Exception:  # noqa: BLE001 - no portal: fall back below
        pass
    settings = Gtk.Settings.get_default()
    if settings is not None:
        if settings.get_property("gtk-application-prefer-dark-theme"):
            return "dark"
        name = (settings.get_property("gtk-theme-name") or "").lower()
        if name:
            return "dark" if "dark" in name else "light"
    return "dark"


_provider = None


def apply_theme(widget, scheme=None):
    """Apply the Linux Studio style (light or dark, following the desktop) to every window on this display."""
    global _provider
    # Every Linux Studio window shows the Linux Studio icon (installed in the system icon theme by the package),
    # instead of the desktop's generic "unknown app" icon.
    Gtk.Window.set_default_icon_name(APP_ICON)
    if _provider is None:
        _provider = Gtk.CssProvider()
        _provider.load_from_data(css_for(scheme or preferred_scheme()))
        Gtk.StyleContext.add_provider_for_display(widget.get_display(), _provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

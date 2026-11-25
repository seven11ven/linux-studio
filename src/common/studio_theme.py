"""Linux Studio window style for the GTK windows on your desktop (pop-up, websites window, first-run).
Shared by every Linux Studio window. Colours come from the approved mockups (project-notes/mockups/linux-studio-mockups.html), dark palette.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

CSS = b"""
window, window.background { background-color: #171e1b; color: #e3ebe7; }
label { color: #e3ebe7; }
.ls-title { font-size: 1.35em; font-weight: 600; }
.ls-muted { color: #97a59f; }
.ls-domain { font-family: monospace; font-size: 1.25em; font-weight: 600; }
.ls-note { background-color: #1c3a2f; border-radius: 6px; padding: 10px 12px; }
.ls-note-warn { background-color: #3a2b17; border-radius: 6px; padding: 10px 12px; }
.ls-term { background-color: #0a0e0d; color: #cfe3da; font-family: monospace; border-radius: 6px; padding: 10px 12px; }
.ls-pill-warn { background-color: #3a2b17; color: #f0a950; border-radius: 99px; padding: 2px 10px; font-size: 0.85em; font-weight: 600; }
.ls-pill-ok { background-color: #1c3a2f; color: #4cc296; border-radius: 99px; padding: 2px 10px; font-size: 0.85em; }
.ls-pill-bad { background-color: #3b1e1c; color: #f2817a; border-radius: 99px; padding: 2px 10px; font-size: 0.85em; }
.ls-error { color: #f2817a; }
entry { background-color: #1d2522; color: #e3ebe7; border: 1px solid #2c3732; border-radius: 6px; font-family: monospace; }
entry:focus-within { border-color: #4cc296; box-shadow: 0 0 0 1px #4cc296; outline: none; }
entry text selection, label selection { background-color: #1c3a2f; color: #e3ebe7; }
button { background-image: none; background-color: #171e1b; color: #e3ebe7; border: 1px solid #2c3732;
         border-radius: 6px; box-shadow: none; padding: 6px 14px; }
button:hover { background-color: #1d2522; }
button.ls-primary { background-color: #4cc296; color: #06130e; border-color: #4cc296; font-weight: 600; }
button.ls-primary:hover { background-color: #5fd3a6; }
button.ls-danger { color: #f2817a; border-color: #f2817a; }
button.ls-link { background-color: transparent; border-color: transparent; color: #97a59f; padding: 2px 0; text-decoration: underline; }
button.ls-link:hover { color: #e3ebe7; background-color: transparent; }
button:disabled { opacity: 0.5; }
button:focus-visible { outline: 2px solid #4cc296; outline-offset: 2px; }
.ls-row { border-bottom: 1px solid #2c3732; padding: 6px 0; }
.ls-header { color: #97a59f; font-size: 0.8em; font-weight: 600; }
headerbar { background-color: #1d2522; color: #e3ebe7; }
.ls-banner { background-color: #1c3a2f; color: #e3ebe7; padding: 10px 16px; }
.ls-side { background-color: #1d2522; border-right: 1px solid #2c3732; padding: 10px; min-width: 170px; }
button.ls-side-item { background-image: none; background-color: transparent; border-color: transparent; box-shadow: none; padding: 8px 10px; }
button.ls-side-item label { color: #e3ebe7; font-weight: normal; }
button.ls-side-item:hover { background-color: #171e1b; }
button.ls-side-item:checked { background-color: #1c3a2f; }
button.ls-side-item:checked label { color: #4cc296; font-weight: 600; }
.ls-subtitle { font-weight: 600; margin-top: 8px; }
.ls-mono { font-family: monospace; }
.ls-pill { background-color: #1d2522; color: #97a59f; border: 1px solid #2c3732; border-radius: 99px; padding: 2px 10px; font-size: 0.85em; }
"""

_provider = None


def apply_theme(widget):
    """Apply the Linux Studio style to every window on this widget's display."""
    global _provider
    if _provider is None:
        _provider = Gtk.CssProvider()
        _provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(widget.get_display(), _provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

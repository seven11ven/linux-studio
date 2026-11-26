#!/usr/bin/python3
"""Linux Studio Settings window (mockup screen 5). Runs on your real desktop, outside the sandbox, so nothing
inside Linux Studio can change these settings. Opened with:  linux-studio --settings

Settings are read and written through the launcher (`--get-clipboard` / `--set-clipboard`), so the rules for the
settings file live in one place.
Usage: settings_window.py <path-to-linux-studio-launcher>
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from studio_theme import apply_theme  # noqa: E402

NOTES = {
    "paste-only": ("Paste only: text you copy elsewhere reaches Linux Studio only when you paste inside its window "
                   "with the keyboard (Ctrl+V or Shift+Insert), once per paste. Code inside can't read your clipboard "
                   "in the background, highlighted text is never shared, and anything copied inside stays inside."),
    "both": ("Both directions: copy and paste work like a normal app. ⚠ Code inside Linux Studio, such as an "
             "extension, could read anything you copy elsewhere, including passwords."),
}


def display_mode():
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    if wayland and os.path.exists(os.path.join(runtime, wayland)):
        return ("Wayland", "Your desktop uses Wayland. Linux Studio opens as a normal window, and Wayland already "
                           "keeps apps from seeing each other.")
    return ("Private X11 window", "Your desktop uses X11, so Linux Studio runs in its own window with a private "
                                  "display. Code inside can only see and type into that window. (This protection is "
                                  "off only if you start Linux Studio with --unsafe-direct-x11.)")


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, launcher):
        super().__init__(application=app, title="Linux Studio · Settings")
        self.launcher = launcher
        self.set_default_size(620, -1)
        self.set_resizable(False)
        apply_theme(self)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(22)
        self.set_child(box)
        title = Gtk.Label(label="Settings", xalign=0)
        title.add_css_class("ls-title")
        box.append(title)

        # Clipboard
        box.append(self.section("Clipboard"))
        row = Gtk.Box(spacing=8)
        self.paste_btn = Gtk.ToggleButton(label="Paste only")
        self.both_btn = Gtk.ToggleButton(label="Both directions", group=self.paste_btn)
        for b in (self.paste_btn, self.both_btn):
            b.add_css_class("ls-choice")
            row.append(b)
        box.append(row)
        self.note = Gtk.Label(xalign=0, wrap=True)
        box.append(self.note)
        current = self.run("--get-clipboard").strip() or "paste-only"
        (self.both_btn if current == "both" else self.paste_btn).set_active(True)
        self.show_note(current)
        self.paste_btn.connect("toggled", self.on_toggle, "paste-only")
        self.both_btn.connect("toggled", self.on_toggle, "both")

        # Display
        box.append(self.section("Display"))
        mode, text = display_mode()
        grid = Gtk.Grid(column_spacing=14, row_spacing=6)
        k1 = Gtk.Label(label="Mode", xalign=0)
        k1.add_css_class("ls-muted")
        v1 = Gtk.Box(spacing=8)
        v1.append(Gtk.Label(label=mode, xalign=0))
        pill = Gtk.Label(label="Isolated")
        pill.add_css_class("ls-pill-ok")
        v1.append(pill)
        k2 = Gtk.Label(label="What this means", xalign=0, valign=Gtk.Align.START)
        k2.add_css_class("ls-muted")
        v2 = Gtk.Label(label=text, xalign=0, wrap=True, hexpand=True)
        grid.attach(k1, 0, 0, 1, 1)
        grid.attach(v1, 1, 0, 1, 1)
        grid.attach(k2, 0, 1, 1, 1)
        grid.attach(v2, 1, 1, 1, 1)
        box.append(grid)

        # More
        box.append(self.section("More"))
        more = Gtk.Box(spacing=8)
        for label, arg in (("Approved websites…", "--network"), ("Toolchains…", "--toolchains")):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, a=arg: subprocess.Popen([self.launcher, a], start_new_session=True))
            more.append(b)
        box.append(more)

        hint = Gtk.Label(xalign=0, wrap=True, label="Saved outside the sandbox, so nothing inside Linux Studio can change "
                         "these settings. Clipboard changes apply immediately.")
        hint.add_css_class("ls-muted")
        box.append(hint)
        self.error = Gtk.Label(xalign=0, wrap=True)
        self.error.add_css_class("ls-error")
        box.append(self.error)

    def section(self, text):
        lab = Gtk.Label(label=text, xalign=0)
        lab.add_css_class("ls-subtitle")
        return lab

    def run(self, *args):
        p = subprocess.run([self.launcher, *args], capture_output=True, text=True, check=False)
        if p.returncode != 0:
            self.error.set_text(p.stderr.strip().removeprefix("linux-studio: ") or "Couldn't save the setting.")
        return p.stdout

    def show_note(self, mode):
        self.note.set_text(NOTES[mode])
        self.note.remove_css_class("ls-note")
        self.note.remove_css_class("ls-note-warn")
        self.note.add_css_class("ls-note-warn" if mode == "both" else "ls-note")

    def on_toggle(self, button, mode):
        if button.get_active():
            self.error.set_text("")
            self.run("--set-clipboard", mode)
            self.show_note(mode)


def main():
    if len(sys.argv) != 2 or not os.access(sys.argv[1], os.X_OK):
        print("Usage: settings_window.py <path-to-linux-studio-launcher>", file=sys.stderr)
        return 2
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.Settings",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", lambda a: SettingsWindow(a, sys.argv[1]).present())
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())

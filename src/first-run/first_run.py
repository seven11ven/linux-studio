#!/usr/bin/python3
"""Linux Studio first-run window: choose the one project folder Linux Studio may see.

Runs on your real desktop (outside the sandbox), before the editor starts.
It asks the launcher to check and save the folder, so the safety rules live in one place
(src/launcher/linux-studio). Exit code 0 = folder saved, 1 = user quit.

Usage: first_run.py <path-to-linux-studio-launcher>
Needs: python3-gi and gir1.2-gtk-4.0 (GTK 4.10 or newer, for the system folder picker).
"""
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

APP_ID = "io.github.seven11ven.linuxstudio.FirstRun"
DEFAULT_FOLDER = "~/LinuxStudio/project-folder"

CSS = b"""
.ls-title { font-size: 1.35em; font-weight: 600; }
.ls-hint { opacity: 0.72; }
.ls-note { background: alpha(#1f7a5c, 0.14); border-radius: 6px; padding: 10px 12px; }
.ls-term { background: #0f1513; color: #cfe3da; font-family: monospace; border-radius: 6px; padding: 10px 12px; }
.ls-error { color: #b3261e; }
"""


class FirstRunWindow(Gtk.ApplicationWindow):
    def __init__(self, app, launcher):
        super().__init__(application=app, title="Linux Studio · Setup")
        self.launcher = launcher
        self.saved = False
        self.set_default_size(620, -1)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(22)
        self.set_child(box)

        title = Gtk.Label(label="Choose your project folder", xalign=0)
        title.add_css_class("ls-title")
        hint = Gtk.Label(xalign=0, wrap=True)
        hint.set_markup("Linux Studio can only see this one folder. Inside the app it always appears as "
                        "<tt>project-folder</tt>.")
        hint.add_css_class("ls-hint")
        box.append(title)
        box.append(hint)

        label = Gtk.Label(label="Location on this computer", xalign=0)
        row = Gtk.Box(spacing=8)
        self.entry = Gtk.Entry(hexpand=True, text=DEFAULT_FOLDER)
        self.entry.connect("activate", self.on_create)
        self.entry.connect("changed", lambda *_: self.error.set_text(""))
        browse = Gtk.Button(label="Browse…")
        browse.connect("clicked", self.on_browse)
        row.append(self.entry)
        row.append(browse)
        tip = Gtk.Label(xalign=0, wrap=True)
        tip.set_markup("You can change this later with <tt>linux-studio --set-project-folder</tt>.")
        tip.add_css_class("ls-hint")
        for w in (label, row, tip):
            box.append(w)

        note = Gtk.Label(xalign=0, wrap=True, label=(
            "The folder will be created if it doesn't exist. Linux Studio can't see your home folder, "
            "other drives or system files."))
        note.add_css_class("ls-note")
        box.append(note)

        box.append(Gtk.Label(label="Inside the app, the terminal will look like this", xalign=0))
        term = Gtk.Label(xalign=0, label=(
            "project-folder $ mkdir apples && cd apples\n"
            "project-folder/apples $ pwd\n"
            "project-folder/apples"))
        term.add_css_class("ls-term")
        box.append(term)

        self.error = Gtk.Label(xalign=0, wrap=True)
        self.error.add_css_class("ls-error")
        box.append(self.error)

        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect("clicked", lambda *_: self.close())
        create = Gtk.Button(label="Create folder and open Linux Studio")
        create.add_css_class("suggested-action")
        create.connect("clicked", self.on_create)
        actions.append(quit_btn)
        actions.append(create)
        box.append(actions)
        self.set_default_widget(create)

    def on_browse(self, _button):
        dialog = Gtk.FileDialog(title="Choose project folder", modal=True)
        start = os.path.expanduser(os.path.dirname(self.entry.get_text().strip()) or "~")
        if os.path.isdir(start):
            dialog.set_initial_folder(Gio.File.new_for_path(start))
        dialog.select_folder(self, None, self.on_browse_done)

    def on_browse_done(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled
        if folder and folder.get_path():
            self.entry.set_text(folder.get_path())

    def on_create(self, *_):
        path = self.entry.get_text().strip()
        # The launcher validates, creates the folder and saves the config (single source of truth).
        proc = subprocess.run([self.launcher, "--set-project-folder", path],
                              capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            msg = proc.stderr.strip().removeprefix("linux-studio: ")
            self.error.set_text(msg[:1].upper() + msg[1:] if msg else "That folder can't be used.")
            return
        self.saved = True
        self.close()


def main():
    if len(sys.argv) != 2 or not os.access(sys.argv[1], os.X_OK):
        print("Usage: first_run.py <path-to-linux-studio-launcher>", file=sys.stderr)
        return 2
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    state = {}

    def on_activate(application):
        win = FirstRunWindow(application, sys.argv[1])
        Gtk.StyleContext.add_provider_for_display(win.get_display(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        state["win"] = win
        win.present()

    app.connect("activate", on_activate)
    app.run([])
    return 0 if state.get("win") and state["win"].saved else 1


if __name__ == "__main__":
    sys.exit(main())

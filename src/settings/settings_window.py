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
from gi.repository import Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from studio_theme import apply_theme  # noqa: E402

NOTES = {
    "paste-only": ("Paste only: text you copy elsewhere reaches Linux Studio only when you paste inside its window "
                   "with the keyboard (Ctrl+V or Shift+Insert), once per paste. Code inside can't read your clipboard "
                   "in the background, highlighted text is never shared, and anything copied inside stays inside."),
    "both": ("Both directions: copy and paste work like a normal app. ⚠ Code inside Linux Studio, such as an "
             "extension, could read anything you copy elsewhere, including passwords."),
}
SIZE_CHOICES = [(256, "256 MB"), (512, "512 MB (default)"), (1024, "1 GB"), (1536, "1.5 GB")]
SIG_NOTES = {
    "check": ("Check signatures: before an extension installs, Linux Studio checks it against the signature Open VSX "
              "published for it. If the signature is missing, wrong or doesn't match the download, the install stops "
              "and the editor asks you; you can still choose \"Install Anyway\"."),
    "off": ("Don't check: extensions install without checking that the download is exactly what Open VSX published. "
            "⚠ A tampered download would not be noticed. Downloads still only come from open-vsx.org over HTTPS."),
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
        self.set_default_size(640, 760)   # fits a 1080p screen; the content scrolls when it's taller
        self.set_size_request(560, 420)
        apply_theme(self)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(22)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(box)
        self.set_child(scroller)
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

        # Extension signatures
        box.append(self.section("Extension signatures"))
        srow = Gtk.Box(spacing=8)
        self.sig_on = Gtk.ToggleButton(label="Check signatures")
        self.sig_off = Gtk.ToggleButton(label="Don't check", group=self.sig_on)
        for b in (self.sig_on, self.sig_off):
            b.add_css_class("ls-choice")
            srow.append(b)
        box.append(srow)
        self.sig_note = Gtk.Label(xalign=0, wrap=True)
        box.append(self.sig_note)
        self.size_row = Gtk.Box(spacing=10)
        self.size_row.append(Gtk.Label(label="Largest extension to check", xalign=0))
        self.size_pick = Gtk.DropDown.new_from_strings([label for _mb, label in SIZE_CHOICES])
        self.size_row.append(self.size_pick)
        box.append(self.size_row)
        self.size_note = Gtk.Label(xalign=0, wrap=True, label=(
            "Extensions bigger than this are refused (you can still choose Install Anyway). A bigger limit lets larger "
            "extensions be checked but uses more memory while checking. Claude Code is about 190 MB."))
        self.size_note.add_css_class("ls-muted")
        box.append(self.size_note)
        current_mb = self.run("--get-extension-size-limit").strip()
        sizes = [mb for mb, _label in SIZE_CHOICES]
        self.size_pick.set_selected(sizes.index(int(current_mb)) if current_mb.isdigit() and int(current_mb) in sizes else 1)
        self.size_pick.connect("notify::selected", self.on_size)
        sig = self.run("--get-extension-signatures").strip() or "check"
        (self.sig_off if sig == "off" else self.sig_on).set_active(True)
        self.show_sig_note(sig)
        self.sig_on.connect("toggled", self.on_sig, "check")
        self.sig_off.connect("toggled", self.on_sig, "off")

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

        # CPU and memory
        box.append(self.section("CPU and memory"))
        res = dict(line.split("=", 1) for line in self.run("--get-resources").splitlines() if "=" in line)
        tc, tm = int(res.get("total_cores", "1")), int(res.get("total_memory_gb", "1"))
        dc, dm = int(res.get("default_cores", "1")), int(res.get("default_memory_gb", "1"))
        self.mem_supported = res.get("memory_limit_supported") == "yes"
        info = Gtk.Label(xalign=0, label=f"This computer: {tc} CPU cores, {tm} GB memory.")
        info.add_css_class("ls-muted")
        box.append(info)
        self.core_opts = [("all", f"All {tc} cores")]
        if tc > 1:
            self.core_opts.append(("default", f"{dc} cores (default: all but one)"))
        for n in sorted({tc - 2, tc // 2, tc // 4, 2, 1}, reverse=True):
            if 1 <= n < dc and str(n) not in [k for k, _l in self.core_opts]:
                self.core_opts.append((str(n), f"{n} core" + ("s" if n > 1 else "")))
        self.mem_opts = [("none", "No limit"), ("default", f"{dm} GB (default: 75%)")]
        for g in sorted({tm // 2, tm // 4, 2, 1}, reverse=True):
            if 1 <= g < dm and str(g) not in [k for k, _l in self.mem_opts]:
                self.mem_opts.append((str(g), f"{g} GB"))
        self.cpu_pick = self.choice_row(box, "CPU cores", self.core_opts, res.get("cores_setting", "default"), "cores")
        self.mem_pick = self.choice_row(box, "Memory limit", self.mem_opts, res.get("memory_setting", "default"), "GB")
        self.res_note = Gtk.Label(xalign=0, wrap=True)
        box.append(self.res_note)
        self.show_res_note()
        self.cpu_pick.connect("notify::selected", self.on_res, "--set-cpu-cores", self.core_opts)
        self.mem_pick.connect("notify::selected", self.on_res, "--set-memory-limit", self.mem_opts)

        # More
        box.append(self.section("More"))
        more = Gtk.Box(spacing=8)
        for label, arg in (("Approved websites…", "--network"), ("Toolchains…", "--toolchains")):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, a=arg: subprocess.Popen([self.launcher, a], start_new_session=True))
            more.append(b)
        box.append(more)

        # Your data
        box.append(self.section("Your data"))
        self.rm_open = Gtk.Button(label="Remove my Linux Studio data…", halign=Gtk.Align.START)
        self.rm_open.add_css_class("ls-danger")
        box.append(self.rm_open)
        self.rm_open.connect("clicked", self.open_remove_dialog)

        hint = Gtk.Label(xalign=0, wrap=True, label="Saved outside the sandbox, so nothing inside Linux Studio can change "
                         "these settings. Clipboard changes apply immediately; the signature setting applies the "
                         "next time Linux Studio starts.")
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

    def choice_row(self, box, label, opts, current, unit):
        if current not in [k for k, _l in opts]:   # a value saved earlier that isn't in the list: show it too
            opts.append((current, f"{current} {unit}"))
        row = Gtk.Box(spacing=10)
        lab = Gtk.Label(label=label, xalign=0)
        lab.set_size_request(130, -1)
        row.append(lab)
        pick = Gtk.DropDown.new_from_strings([l for _k, l in opts])
        pick.set_selected([k for k, _l in opts].index(current))
        row.append(pick)
        box.append(row)
        return pick

    def show_res_note(self):
        text = ("Covers everything inside Linux Studio: the editor, extensions (such as Claude Code) and anything you run in "
                "its terminal. Programs inside see only the cores you allow, so builds don't try to use more. Applies the "
                "next time Linux Studio starts.")
        mem_key = self.mem_opts[self.mem_pick.get_selected()][0]
        limited = mem_key != "none"
        if limited:
            text += (f" ⚠ With a memory limit, if Linux Studio needs more than {self.mem_opts[self.mem_pick.get_selected()][1].split(' (')[0]}, "
                     "the biggest program inside it (often a build or an extension) is stopped. Save your work often.")
            if not self.mem_supported:
                text += (" This computer can't enforce a memory limit right now (it needs systemd's user session), so "
                         "Linux Studio will start without one.")
        self.res_note.set_text(text)
        for c in ("ls-note", "ls-note-warn"):
            self.res_note.remove_css_class(c)
        self.res_note.add_css_class("ls-note-warn" if limited else "ls-note")

    def on_res(self, dropdown, _pspec, option, opts):
        self.error.add_css_class("ls-error")
        self.error.set_text("")
        self.run(option, opts[dropdown.get_selected()][0])
        self.show_res_note()

    def show_sig_note(self, mode):
        self.sig_note.set_text(SIG_NOTES[mode])
        self.sig_note.remove_css_class("ls-note")
        self.sig_note.remove_css_class("ls-note-warn")
        self.sig_note.add_css_class("ls-note-warn" if mode == "off" else "ls-note")
        self.size_row.set_visible(mode != "off")
        self.size_note.set_visible(mode != "off")

    def on_size(self, dropdown, _pspec):
        self.error.add_css_class("ls-error")
        self.error.set_text("")
        self.run("--set-extension-size-limit", str(SIZE_CHOICES[dropdown.get_selected()][0]))

    def on_sig(self, button, mode):
        if button.get_active():
            self.error.set_text("")
            self.run("--set-extension-signatures", mode)
            self.show_sig_note(mode)

    def open_remove_dialog(self, _button):
        """The "Are you sure?" confirmation, as its own pop-up window in front of Settings (PM decision)."""
        dlg = Gtk.Window(title="Linux Studio · Remove your data", transient_for=self, modal=True, resizable=False)
        dlg.set_default_size(480, -1)
        apply_theme(dlg)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(20)
        dlg.set_child(box)
        pill = Gtk.Label(label="Can't be undone", halign=Gtk.Align.START)
        pill.add_css_class("ls-pill-warn")
        box.append(pill)
        head = Gtk.Label(label="Are you sure you want to remove your Linux Studio data?", xalign=0, wrap=True)
        head.add_css_class("ls-subtitle")
        box.append(head)
        box.append(Gtk.Label(xalign=0, wrap=True, label="Close Linux Studio first. Choose what to delete from this computer."))
        self.rm_parts = {}
        for key, label, default in (("extensions", "Extensions, editor settings and logins (for example Claude's)", True),
                                    ("toolchains", "Toolchains you installed", True),
                                    ("settings", "My Settings choices and approved websites", False)):
            c = Gtk.CheckButton(label=label, active=default)
            self.rm_parts[key] = c
            box.append(c)
        box.append(Gtk.Label(xalign=0, wrap=True, label="Your project folder is never touched."))
        self.rm_msg = Gtk.Label(xalign=0, wrap=True)
        self.rm_msg.add_css_class("ls-error")
        box.append(self.rm_msg)
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        go = Gtk.Button(label="Remove selected", sensitive=False)   # unlocks after 1 second, so a stray click can't delete
        go.add_css_class("ls-danger")
        actions.append(cancel)
        actions.append(go)
        box.append(actions)
        cancel.connect("clicked", lambda _b: dlg.close())
        go.connect("clicked", self.on_remove, dlg)
        dlg.set_default_widget(cancel)   # Enter cancels
        cancel.grab_focus()
        GLib.timeout_add(1000, lambda: go.set_sensitive(True) or False)
        dlg.present()

    def on_remove(self, _button, dlg):
        self.rm_msg.set_text("")
        parts = [k for k, c in self.rm_parts.items() if c.get_active()]
        if not parts:
            self.rm_msg.set_text("Nothing selected, so nothing was removed.")
            return
        if self.run("--is-running").strip() == "yes":
            self.rm_msg.set_text("Linux Studio is still open. Close it (and the Toolchains window) first, then try again.")
            return
        p = subprocess.run([self.launcher, "--remove-my-data-now", ",".join(parts)],
                           capture_output=True, text=True, check=False)
        if p.returncode != 0:
            self.rm_msg.set_text(p.stderr.strip().removeprefix("linux-studio: ") or "Couldn't remove the data.")
            return
        dlg.close()
        self.error.remove_css_class("ls-error")
        self.error.set_text("Removed: " + ", ".join(parts) + ". Your project folder was not touched.")
        if "settings" in parts:   # don't touch the toggles here: that would write a new settings file straight away
            self.error.set_text(self.error.get_text() + " Settings are back to their defaults; reopen this window to see them.")

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

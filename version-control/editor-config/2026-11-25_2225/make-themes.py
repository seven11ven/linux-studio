#!/usr/bin/env python3
"""Generates Linux Studio's VS Code themes (src/editor/theme/themes/) from the mockup palette.
The palette below is copied from project-notes/mockups/linux-studio-mockups.html, the source of truth.
Usage: scripts/make-themes.py src/editor/theme/themes
"""
import json
import os
import sys

OUT = sys.argv[1]

PALETTES = {
    "dark": dict(bg="#0f1412", surface="#171e1b", panel="#1d2522", ink="#e3ebe7", muted="#97a59f", line="#2c3732",
                 accent="#4cc296", accent_ink="#06130e", accent_soft="#1c3a2f", warn="#f0a950", warn_soft="#3a2b17",
                 bad="#f2817a", bad_soft="#3b1e1c", term="#0a0e0d", term_ink="#cfe3da",
                 # code colours (derived from the palette's hues)
                 kw="#4cc296", str="#e9b872", num="#f0a950", fn="#8fd3f4", type="#7fd8b2", comment="#6f7d77", var="#e3ebe7",
                 ansi=["#2c3732", "#f2817a", "#4cc296", "#f0a950", "#8fd3f4", "#c9a0f0", "#7fd8b2", "#cfe3da",
                       "#6f7d77", "#f7a29c", "#7fd8b2", "#f5c27c", "#b2e2f8", "#dcc0f6", "#a9e8cd", "#ffffff"]),
    "light": dict(bg="#eef1f0", surface="#ffffff", panel="#f5f7f6", ink="#17201d", muted="#5b6762", line="#d5dcd9",
                  accent="#1f7a5c", accent_ink="#ffffff", accent_soft="#dcefe7", warn="#a35a00", warn_soft="#fbeedb",
                  bad="#b3261e", bad_soft="#fbe3e1", term="#0f1513", term_ink="#cfe3da",
                  kw="#1f7a5c", str="#9a5b00", num="#a35a00", fn="#1d5f8a", type="#0f6b4c", comment="#7a8781", var="#17201d",
                  ansi=["#2c3732", "#f2817a", "#4cc296", "#f0a950", "#8fd3f4", "#c9a0f0", "#7fd8b2", "#cfe3da",
                        "#6f7d77", "#f7a29c", "#7fd8b2", "#f5c27c", "#b2e2f8", "#dcc0f6", "#a9e8cd", "#ffffff"]),
}
ANSI = ["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]


def theme(name, kind, p):
    c = {
        # base
        "focusBorder": p["accent"], "foreground": p["ink"], "descriptionForeground": p["muted"],
        "errorForeground": p["bad"], "icon.foreground": p["muted"], "widget.border": p["line"],
        "selection.background": p["accent_soft"], "textLink.foreground": p["accent"], "textLink.activeForeground": p["accent"],
        "textPreformat.foreground": p["ink"], "textBlockQuote.background": p["panel"], "textCodeBlock.background": p["panel"],
        "sash.hoverBorder": p["accent"], "progressBar.background": p["accent"],
        # window / title
        "titleBar.activeBackground": p["panel"], "titleBar.activeForeground": p["ink"],
        "titleBar.inactiveBackground": p["panel"], "titleBar.inactiveForeground": p["muted"], "titleBar.border": p["line"],
        "menubar.selectionBackground": p["accent_soft"], "menu.background": p["surface"], "menu.foreground": p["ink"],
        "menu.selectionBackground": p["accent_soft"], "menu.selectionForeground": p["ink"], "menu.separatorBackground": p["line"],
        "menu.border": p["line"], "commandCenter.background": p["surface"], "commandCenter.border": p["line"],
        "commandCenter.foreground": p["ink"], "commandCenter.activeBackground": p["accent_soft"],
        # activity bar / side bar
        "activityBar.background": p["bg"], "activityBar.foreground": p["accent"], "activityBar.inactiveForeground": p["muted"],
        "activityBar.border": p["line"], "activityBar.activeBorder": p["accent"], "activityBar.activeBackground": p["panel"],
        "activityBarBadge.background": p["accent"], "activityBarBadge.foreground": p["accent_ink"],
        "sideBar.background": p["panel"], "sideBar.foreground": p["ink"], "sideBar.border": p["line"],
        "sideBarTitle.foreground": p["ink"], "sideBarSectionHeader.background": p["panel"],
        "sideBarSectionHeader.foreground": p["ink"], "sideBarSectionHeader.border": p["line"],
        # lists
        "list.activeSelectionBackground": p["accent_soft"], "list.activeSelectionForeground": p["ink"],
        "list.inactiveSelectionBackground": p["accent_soft"], "list.hoverBackground": p["surface"],
        "list.focusOutline": p["accent"], "list.highlightForeground": p["accent"], "list.errorForeground": p["bad"],
        "list.warningForeground": p["warn"], "tree.indentGuidesStroke": p["line"],
        # editor
        "editor.background": p["surface"], "editor.foreground": p["ink"],
        "editorLineNumber.foreground": p["muted"] + "99", "editorLineNumber.activeForeground": p["ink"],
        "editorCursor.foreground": p["accent"], "editor.selectionBackground": p["accent_soft"],
        "editor.inactiveSelectionBackground": p["accent_soft"] + "99", "editor.lineHighlightBackground": p["panel"],
        "editor.lineHighlightBorder": "#00000000", "editor.findMatchBackground": p["warn_soft"],
        "editor.findMatchHighlightBackground": p["warn_soft"] + "99", "editor.wordHighlightBackground": p["accent_soft"] + "99",
        "editorIndentGuide.background1": p["line"], "editorIndentGuide.activeBackground1": p["muted"],
        "editorWhitespace.foreground": p["line"], "editorRuler.foreground": p["line"],
        "editorBracketMatch.background": p["accent_soft"], "editorBracketMatch.border": p["accent"],
        "editorError.foreground": p["bad"], "editorWarning.foreground": p["warn"], "editorInfo.foreground": p["accent"],
        "editorGutter.addedBackground": p["accent"], "editorGutter.modifiedBackground": p["warn"], "editorGutter.deletedBackground": p["bad"],
        "editorWidget.background": p["panel"], "editorWidget.border": p["line"], "editorHoverWidget.background": p["panel"],
        "editorHoverWidget.border": p["line"], "editorSuggestWidget.background": p["panel"], "editorSuggestWidget.border": p["line"],
        "editorSuggestWidget.selectedBackground": p["accent_soft"], "editorGroupHeader.tabsBackground": p["panel"],
        "editorGroupHeader.tabsBorder": p["line"], "editorGroup.border": p["line"],
        "minimap.background": p["surface"], "scrollbarSlider.background": p["muted"] + "33",
        "scrollbarSlider.hoverBackground": p["muted"] + "55", "scrollbarSlider.activeBackground": p["muted"] + "77",
        # tabs
        "tab.activeBackground": p["surface"], "tab.activeForeground": p["ink"], "tab.activeBorderTop": p["accent"],
        "tab.inactiveBackground": p["panel"], "tab.inactiveForeground": p["muted"], "tab.border": p["line"],
        "tab.hoverBackground": p["surface"], "tab.unfocusedActiveBorderTop": p["line"],
        # panel / terminal
        "panel.background": p["panel"], "panel.border": p["line"], "panelTitle.activeForeground": p["ink"],
        "panelTitle.activeBorder": p["accent"], "panelTitle.inactiveForeground": p["muted"],
        "terminal.background": p["term"], "terminal.foreground": p["term_ink"], "terminalCursor.foreground": p["accent"],
        "terminal.selectionBackground": "#4cc29644", "terminal.border": p["line"],
        # status bar
        "statusBar.background": p["bg"], "statusBar.foreground": p["muted"], "statusBar.border": p["line"],
        "statusBar.noFolderBackground": p["bg"], "statusBar.debuggingBackground": p["warn"],
        "statusBar.debuggingForeground": p["accent_ink"], "statusBarItem.hoverBackground": p["panel"],
        "statusBarItem.remoteBackground": p["accent"], "statusBarItem.remoteForeground": p["accent_ink"],
        "statusBarItem.prominentBackground": p["accent_soft"], "statusBarItem.errorBackground": p["bad"],
        "statusBarItem.warningBackground": p["warn"],
        # buttons / inputs / badges
        "button.background": p["accent"], "button.foreground": p["accent_ink"], "button.hoverBackground": p["accent"] + "dd",
        "button.secondaryBackground": p["surface"], "button.secondaryForeground": p["ink"],
        "button.secondaryHoverBackground": p["panel"], "button.border": p["line"],
        "input.background": p["panel"], "input.foreground": p["ink"], "input.border": p["line"],
        "input.placeholderForeground": p["muted"], "inputOption.activeBorder": p["accent"],
        "inputValidation.errorBackground": p["bad_soft"], "inputValidation.errorBorder": p["bad"],
        "dropdown.background": p["panel"], "dropdown.border": p["line"], "dropdown.foreground": p["ink"],
        "checkbox.background": p["panel"], "checkbox.border": p["line"],
        "badge.background": p["accent_soft"], "badge.foreground": p["accent"],
        # notifications / quick input / banner
        "notifications.background": p["panel"], "notifications.foreground": p["ink"], "notifications.border": p["line"],
        "notificationCenterHeader.background": p["panel"], "notificationLink.foreground": p["accent"],
        "quickInput.background": p["panel"], "quickInput.foreground": p["ink"], "quickInputTitle.background": p["panel"],
        "quickInputList.focusBackground": p["accent_soft"], "pickerGroup.foreground": p["accent"],
        "banner.background": p["warn_soft"], "banner.foreground": p["ink"], "banner.iconForeground": p["warn"],
        # welcome page
        "welcomePage.background": p["surface"], "welcomePage.tileBackground": p["panel"],
        "welcomePage.tileHoverBackground": p["accent_soft"], "welcomePage.tileBorder": p["line"],
        "welcomePage.progress.foreground": p["accent"], "walkThrough.embeddedEditorBackground": p["panel"],
        # misc
        "breadcrumb.foreground": p["muted"], "breadcrumb.focusForeground": p["ink"], "breadcrumb.background": p["surface"],
        "gitDecoration.modifiedResourceForeground": p["warn"], "gitDecoration.untrackedResourceForeground": p["accent"],
        "gitDecoration.deletedResourceForeground": p["bad"], "gitDecoration.ignoredResourceForeground": p["muted"],
        "settings.headerForeground": p["ink"], "settings.modifiedItemIndicator": p["accent"],
        "keybindingLabel.background": p["panel"], "keybindingLabel.border": p["line"], "keybindingLabel.foreground": p["ink"],
    }
    for i, n in enumerate(ANSI):
        c[f"terminal.ansi{n}"] = p["ansi"][i]
        c[f"terminal.ansiBright{n}"] = p["ansi"][i + 8]
    tokens = [
        ("Comments", ["comment", "punctuation.definition.comment"], p["comment"], "italic"),
        ("Keywords", ["keyword", "storage", "storage.type", "keyword.control"], p["kw"], ""),
        ("Strings", ["string", "string.quoted", "markup.inline.raw"], p["str"], ""),
        ("Numbers and constants", ["constant.numeric", "constant.language", "constant.character"], p["num"], ""),
        ("Functions", ["entity.name.function", "support.function", "meta.function-call"], p["fn"], ""),
        ("Types and classes", ["entity.name.type", "entity.name.class", "support.type", "support.class"], p["type"], ""),
        ("Variables", ["variable", "variable.parameter", "meta.definition.variable"], p["var"], ""),
        ("Tags and attributes", ["entity.name.tag", "entity.other.attribute-name"], p["kw"], ""),
        ("Headings", ["markup.heading", "entity.name.section"], p["accent"], "bold"),
        ("Invalid", ["invalid"], p["bad"], ""),
    ]
    return {
        "$schema": "vscode://schemas/color-theme", "name": name, "type": kind, "semanticHighlighting": True,
        "colors": c,
        "tokenColors": [{"name": n, "scope": s, "settings": {"foreground": f, **({"fontStyle": st} if st else {})}}
                        for n, s, f, st in tokens],
    }


os.makedirs(OUT, exist_ok=True)
for key, name, kind in (("dark", "Linux Studio Dark", "dark"), ("light", "Linux Studio Light", "light")):
    with open(os.path.join(OUT, f"linux-studio-{key}.json"), "w") as f:
        json.dump(theme(name, kind, PALETTES[key]), f, indent=2)
        f.write("\n")
print("written")

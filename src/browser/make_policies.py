#!/usr/bin/env python3
"""Writes the Studio Browser's locked policy file (policies.json) from your Settings choices.

Runs OUTSIDE the sandbox, in the launcher, just before the Studio Browser starts. The file is then given to the
browser read-only, so nothing inside Linux Studio can change it. The browser engine is Debian's Firefox ESR; these
are its enterprise policies (https://mozilla.github.io/policy-templates/).

Usage:
  make_policies.py --out FILE [--remember on|off] [--safe-browsing on|off]
                   [--ublock on|off] [--noscript on|off] [--clearurls on|off] [--bitwarden on|off]
Defaults are the PM-approved ones: remember off, Safe Browsing off, all four extensions on.
Standard library only.
"""
import argparse
import json
import os
import sys
import tempfile

PROXY = "127.0.0.1:3128"                      # Linux Studio's approval proxy, as seen inside the sandbox
EXT_DIR = "/run/linux-studio/browser-extensions"  # read-only inside the sandbox (from build-cache/browser-extensions)
DOWNLOADS = "/project-folder/Downloads"       # the only folder of yours the browser can see (PM)
LINK_HELPER = "/run/linux-studio/bin/xdg-open"  # sends linux-studio:// sign-in links back through the link router

UBLOCK = "uBlock0@raymondhill.net"            # from Debian, in the runtime's system extensions folder
MOZILLA_SIGNED = {                            # from addons.mozilla.org, pinned in scripts/fetch-browser-extensions.sh
    "noscript": "{73a6fe31-595d-460b-a920-fcc0f8843232}",
    "clearurls": "{74145f27-f039-47ce-a470-a662b129930a}",
    "bitwarden": "{446900e4-71c2-419f-a6a7-df9c091e268b}",
}


def locked(value):
    return {"Value": value, "Status": "locked"}


def build(remember, safe_browsing, ext_on):
    sb = bool(safe_browsing)
    prefs = {
        # Safe Browsing (PM: a toggle, off by default). Download checks that send file details to Google stay off.
        "browser.safebrowsing.malware.enabled": locked(sb),
        "browser.safebrowsing.phishing.enabled": locked(sb),
        "browser.safebrowsing.blockedURIs.enabled": locked(sb),
        "browser.safebrowsing.downloads.enabled": locked(sb),
        "browser.safebrowsing.downloads.remote.enabled": locked(False),
        # Background connections that would otherwise fill the Network inbox at every start
        "network.captive-portal-service.enabled": locked(False),
        "network.connectivity-service.enabled": locked(False),
        "browser.region.update.enabled": locked(False),
        "browser.region.network.url": locked(""),
        # (Studies and Normandy are switched off by DisableFirefoxStudies; their prefs can't be set here.)
        "browser.discovery.enabled": locked(False),
        "extensions.getAddons.cache.enabled": locked(False),
        "extensions.htmlaboutaddons.recommendations.enabled": locked(False),
        "media.gmp-provider.enabled": locked(False),
        "media.eme.enabled": locked(False),
        "network.prefetch-next": locked(False),
        "network.dns.disablePrefetch": locked(True),
        "browser.places.speculativeConnect.enabled": locked(False),
        "browser.urlbar.speculativeConnect.enabled": locked(False),
        "browser.newtabpage.activity-stream.feeds.telemetry": locked(False),
        "browser.newtabpage.activity-stream.telemetry": locked(False),
        # Extensions: only those this file installs; the system folder holds Debian's uBlock Origin
        "extensions.autoDisableScopes": locked(0),
        "extensions.update.enabled": locked(False),
        "xpinstall.signatures.required": locked(True),
        # Logins, cookies and passwords (PM: a toggle, off by default)
        "signon.rememberSignons": locked(bool(remember)),
    }
    ext = {"*": {"installation_mode": "blocked",
                 "blocked_install_message": "Studio Browser: extensions are chosen in Linux Studio's Settings."}}
    ext[UBLOCK] = {"installation_mode": "allowed" if ext_on["ublock"] else "blocked"}
    for key, ext_id in MOZILLA_SIGNED.items():
        if ext_on[key]:
            ext[ext_id] = {"installation_mode": "force_installed", "updates_disabled": True,
                           "install_url": f"file://{EXT_DIR}/{ext_id}.xpi"}
        else:
            ext[ext_id] = {"installation_mode": "blocked"}

    p = {
        "DisableTelemetry": True, "DisableFirefoxStudies": True, "DisablePocket": True,
        "DisableFeedbackCommands": True, "DisableFirefoxAccounts": True, "DisableAppUpdate": True,
        "DisableProfileImport": True, "DisableSetDesktopBackground": True, "DontCheckDefaultBrowser": True,
        "NoDefaultBookmarks": True, "OverrideFirstRunPage": "", "OverridePostUpdatePage": "",
        "BlockAboutConfig": True, "BlockAboutProfiles": True,
        "CaptivePortal": False, "NetworkPrediction": False, "SearchSuggestEnabled": False,
        "DNSOverHTTPS": {"Enabled": False, "Locked": True},
        "Proxy": {"Mode": "manual", "HTTPProxy": PROXY, "SSLProxy": PROXY, "UseHTTPProxyForAllProtocols": True,
                  "Passthrough": "", "Locked": True},
        "EnableTrackingProtection": {"Value": True, "Locked": True, "Cryptomining": True,
                                     "Fingerprinting": True, "EmailTracking": True},
        "FirefoxHome": {"Search": False, "TopSites": False, "SponsoredTopSites": False, "Highlights": False,
                        "Pocket": False, "SponsoredPocket": False, "Snippets": False, "Locked": True},
        "FirefoxSuggest": {"WebSuggestions": False, "SponsoredSuggestions": False, "ImproveSuggest": False,
                           "Locked": True},
        "UserMessaging": {"ExtensionRecommendations": False, "FeatureRecommendations": False,
                          "UrlbarInterventions": False, "SkipOnboarding": True, "MoreFromMozilla": False,
                          "FirefoxLabs": False, "Locked": True},
        "PasswordManagerEnabled": bool(remember), "OfferToSaveLogins": bool(remember),
        "DownloadDirectory": DOWNLOADS, "PromptForDownloadLocation": False,
        "Handlers": {"schemes": {"linux-studio": {"action": "useHelperApp", "ask": False,
                                                  "handlers": [{"name": "Linux Studio", "path": LINK_HELPER}]}}},
        "ExtensionSettings": ext,
        "Preferences": prefs,
    }
    if not remember:
        # The profile is also kept in memory only and deleted on close; this is a second layer.
        p["SanitizeOnShutdown"] = {"Cache": True, "Cookies": True, "History": True, "Sessions": True,
                                   "FormData": True, "SiteSettings": False, "Locked": True}
    return {"policies": p}


def on_off(v):
    if v not in ("on", "off"):
        raise argparse.ArgumentTypeError("use on or off")
    return v == "on"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--remember", type=on_off, default=False)
    ap.add_argument("--safe-browsing", type=on_off, default=False)
    for name in ("ublock", "noscript", "clearurls", "bitwarden"):
        ap.add_argument(f"--{name}", type=on_off, default=True)
    a = ap.parse_args(argv)
    data = build(a.remember, a.safe_browsing,
                 {"ublock": a.ublock, "noscript": a.noscript, "clearurls": a.clearurls, "bitwarden": a.bitwarden})
    out_dir = os.path.dirname(os.path.abspath(a.out))
    # Write next to the target, then rename, so the browser never reads a half-written file. Never follow links.
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".policies-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(tmp, 0o644)
        os.replace(tmp, a.out)
    except BaseException:
        os.unlink(tmp)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env bash
# Tests the Studio Browser's locked policy file and extension switches (step 2), with no network at all.
# The browser runs headless inside the runtime with a throwaway profile; nothing outside a temp folder is touched.
# Usage: tests/studio-browser-test.sh --runtime-dir <rootfs>
# Needs: build-cache/browser-extensions (scripts/fetch-browser-extensions.sh), bwrap, python3, unzip
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; GEN="$ROOT/src/browser/make_policies.py"; EXT="$ROOT/build-cache/browser-extensions"
[[ "${1:-}" == --runtime-dir && -n "${2:-}" ]] || { echo "Usage: $0 --runtime-dir <rootfs>" >&2; exit 2; }
R="$(realpath "$2")"; FX="$R/usr/lib/firefox-esr"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0; ok(){ echo "PASS  $1"; pass=$((pass+1)); }; bad(){ echo "FAIL  $1"; fail=$((fail+1)); }
mkdir -p "$T/pol" "$T/profile" "$T/dl"

run_browser(){  # starts the browser headless for $1 seconds, with no network, then stops it
  timeout -s TERM "$1" bwrap --unshare-all --die-with-parent --new-session --clearenv \
    --setenv HOME /home/user --setenv MOZ_CRASHREPORTER_DISABLE 1 --setenv PATH /usr/bin:/bin \
    --ro-bind "$R" / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /run --tmpfs /home/user --tmpfs /project-folder \
    --ro-bind "$EXT" /run/linux-studio/browser-extensions --ro-bind "$T/pol" /usr/lib/firefox-esr/distribution \
    --bind "$T/profile" /home/user/profile --bind "$T/dl" /project-folder/Downloads \
    /usr/bin/firefox-esr --headless --no-remote --profile /home/user/profile about:blank >"$T/browser.log" 2>&1
}
active(){  # prints the names of active, non-built-in extensions
  python3 -I - "$T/profile/extensions.json" <<'EOF'
import json,sys
for a in json.load(open(sys.argv[1]))['addons']:
    if a.get('active') and not a.get('location','').startswith('app-builtin'):
        print(a['defaultLocale'].get('name','?'), a.get('signedState'))
EOF
}

# 1. The downloaded extensions are exactly the pinned files
(cd "$EXT" 2>/dev/null && sha256sum --check --strict --status SHA256SUMS) && ok "Downloaded extensions match their pinned SHA-256" || bad "extension checksums (run scripts/fetch-browser-extensions.sh)"

# 2. The policy file is valid and uses only policies and preferences this browser version accepts
python3 -I "$GEN" --out "$T/pol/policies.json" && ok "Policy file written" || bad "policy file written"
unzip -p "$FX/browser/omni.ja" modules/policies/policies-schema.json > "$T/schema.json"
unzip -p "$FX/browser/omni.ja" modules/policies/Policies.sys.mjs > "$T/Policies.mjs"
unzip -p "$FX/omni.ja" modules/AppConstants.sys.mjs > "$T/AppConstants.mjs"
python3 -I - "$T/schema.json" "$T/pol/policies.json" "$T/Policies.mjs" "$T/AppConstants.mjs" <<'EOF' && ok "Every policy and locked preference is accepted by the browser" || bad "unknown policy or preference"
import json,re,sys
sch=json.load(open(sys.argv[1]))['properties']; pol=json.load(open(sys.argv[2]))['policies']; src=open(sys.argv[3]).read()
def lst(name):  # the quoted strings in the browser's own list called <name>
    b=src[src.index(name+' = ['):]; return re.findall(r'"([^"]+)"',b[:b.index('];')])
prefixes=lst('allowedPrefixes'); security=lst('allowedSecurityPrefs'); blocked=lst('blockedPrefs')
if re.search(r'MOZ_REQUIRE_SIGNING:\s*false',open(sys.argv[4]).read()): prefixes.append('xpinstall.signatures.required')
def accepted(p):
    if p in blocked: return False
    if p.startswith('security.'): return p in security
    return any(p.startswith(a) for a in prefixes)
bad=[k for k in pol if k not in sch]+[p for p in pol['Preferences'] if not accepted(p)]
print('  rejected:',bad) if bad else None; sys.exit(1 if bad else 0)
EOF
grep -qE 'MOZ_REQUIRE_SIGNING:\s*false' "$T/AppConstants.mjs" && python3 -I -c "import json,sys;p=json.load(open(sys.argv[1]))['policies']['Preferences']['xpinstall.signatures.required'];sys.exit(0 if p=={'Value':True,'Status':'locked'} else 1)" "$T/pol/policies.json" \
  && ok "Extension signature checks are locked on (this build doesn't force them by itself)" || { grep -qE 'MOZ_REQUIRE_SIGNING:\s*true' "$T/AppConstants.mjs" && ok "Extension signature checks are forced by the build" || bad "signature checks locked on"; }
python3 -I - "$T/pol/policies.json" <<'EOF' && ok "Defaults: Safe Browsing off, remember off, proxy locked to Linux Studio's, telemetry off" || bad "default policy values"
import json,sys
p=json.load(open(sys.argv[1]))['policies']; pr=p['Preferences']
assert pr['browser.safebrowsing.malware.enabled']['Value'] is False and pr['browser.safebrowsing.phishing.enabled']['Value'] is False
assert p['PasswordManagerEnabled'] is False and p['SanitizeOnShutdown']['Cookies'] is True
assert p['Proxy']['Locked'] and p['Proxy']['HTTPProxy']=='127.0.0.1:3128' and p['DNSOverHTTPS']['Enabled'] is False
assert p['DisableTelemetry'] and p['DisableFirefoxStudies'] and p['ExtensionSettings']['*']['installation_mode']=='blocked'
assert p['DownloadDirectory']=='/project-folder/Downloads'
assert pr['security.OCSP.enabled']['Value']==0 and pr['security.ssl.enable_ocsp_stapling']['Value'] is True
EOF
python3 -I "$GEN" --out "$T/x.json" --remember maybe >/dev/null 2>&1 && bad "bad value rejected" || ok "Unknown setting value rejected"

# 3. With every switch on, all four extensions load, and the Mozilla-signed ones pass the signature check
run_browser 25; out="$(active)"
for n in "uBlock Origin" NoScript ClearURLs "Bitwarden Password Manager"; do
  grep -q "^$n " <<<"$out" && ok "$n is active" || bad "$n active"; done
[[ "$(grep -cE '^(NoScript|ClearURLs|Bitwarden Password Manager) 2$' <<<"$out")" == 3 ]] && ok "NoScript, ClearURLs and Bitwarden pass Mozilla's signature check" || bad "signature state"
grep -qiE 'polic(y|ies).*(error|invalid|unknown)' "$T/browser.log" && bad "policy errors logged" || ok "No policy errors logged"

# 4. Switches off remove the extension at the next start; the others stay
python3 -I "$GEN" --out "$T/pol/policies.json" --noscript off --ublock off; run_browser 20; out="$(active)"
! grep -q '^NoScript ' <<<"$out" && ! grep -q '^uBlock Origin ' <<<"$out" && ok "Turned-off extensions are gone" || bad "turned-off extensions gone"
grep -q '^ClearURLs ' <<<"$out" && grep -q '^Bitwarden' <<<"$out" && ok "Other extensions stay on" || bad "others stay on"
python3 -I "$GEN" --out "$T/pol/policies.json"; run_browser 20; out="$(active)"
grep -q '^NoScript ' <<<"$out" && grep -q '^uBlock Origin ' <<<"$out" && ok "Turned back on, they return" || bad "turned back on"

echo; echo "$pass passed, $fail failed"; (( fail == 0 ))

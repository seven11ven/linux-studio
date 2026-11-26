#!/usr/bin/env bash
# Tests Linux Studio's in-sandbox xdg-open (src/launcher/xdg-open), the link router (src/editor/link-router) and the
# browser patch's callback rule (src/editor/patches/browser-callbacks.patch), without the editor: a stand-in editor
# records what it was asked to open. Needs: bwrap, node, python3. Usage: tests/link-router-test.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0; ok(){ echo "PASS  $1"; pass=$((pass+1)); }; bad(){ echo "FAIL  $1${2:+ (got: $2)}"; fail=$((fail+1)); }
KEY="$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')"; echo "$KEY" > "$T/key"
mkdir -p "$T/app/bin"
printf '#!/bin/sh\necho "$4" > /tmp/out/opened\n' > "$T/app/bin/linux-studio-editor"; chmod +x "$T/app/bin/linux-studio-editor"
run() {   # run LINK...: the shim inside a small sandbox with the stand-in editor at /app and the session key
  mkdir -p "$T/out"; rm -f "$T/out/opened"
  bwrap --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --ro-bind /etc /etc \
    --tmpfs /tmp --bind "$T/out" /tmp/out --ro-bind "$T/app" /app --dev /dev --proc /proc \
    --dir /run/linux-studio --ro-bind "$T/key" /run/linux-studio/link-token \
    --ro-bind "$ROOT/src/launcher/xdg-open" /tmp/xdg-open bash /tmp/xdg-open "$@" 2>"$T/out/err"
  echo $?
}
opened() { cat "$T/out/opened" 2>/dev/null; }
b64() { python3 -I -c 'import base64,sys; print(base64.urlsafe_b64encode(sys.argv[1].encode()).rstrip(b"=").decode())' "$1"; }

for link in 'https://example.com/a?b=1&c=2+3' 'https://evil.example%2F@good.example/' 'http://127.0.0.1:47123/start?x=%2Fy'; do
  [[ "$(run "$link")" == 0 && "$(opened)" == "linux-studio://linux-studio.link-router/open?u=$(b64 "$link")&k=$KEY" ]] \
    && ok "Web link sent to the router unchanged (base64url + session key): $link" || bad "web link $link" "$(opened)"
done
[[ "$(run 'linux-studio://pub.ext/callback?code=42')" == 0 && "$(opened)" == "linux-studio://pub.ext/callback?code=42" ]] \
  && ok "linux-studio:// sign-in callback is handed back to the editor" || bad "callback" "$(opened)"
for link in 'file:///etc/passwd' 'mailto:someone@example.com' 'ssh://host' 'javascript:alert(1)' 'vscode://x.y/z' 'HTTPS' \
            'linux-studio://file/etc/passwd' 'linux-studio://linux-studio.link-router/open?u=x' 'linux-studio://-x'; do
  [[ "$(run "$link")" != 0 && -z "$(opened)" ]] && ok "Refused: $link" || bad "refuse $link" "$(opened)"
done
[[ "$(run 'https://a.com' 'https://b.com')" != 0 && -z "$(opened)" ]] && ok "Refused: more than one link" || bad "two links"
[[ "$(run "https://example.com/$(head -c 9000 /dev/zero | tr '\0' a)")" != 0 && -z "$(opened)" ]] && ok "Refused: overlong link" || bad "overlong"
[[ "$(run $'https://example.com/\nx')" != 0 && -z "$(opened)" ]] && ok "Refused: link with a line break" || bad "control chars"
rm "$T/key"; touch "$T/key"
[[ "$(run 'https://example.com/')" != 0 && -z "$(opened)" ]] && ok "Refused: no session key available" || bad "no key"
echo "$KEY" > "$T/key"

# The router and the browser patch's rule (run in node with a stand-in "vscode" module).
cat > "$T/check.cjs" <<'JS'
const Module = require('module'); const orig = Module._load; const fs = require('fs');
const [routerPath, keyFile, patchPath] = process.argv.slice(2);
const realRead = fs.readFileSync;
fs.readFileSync = (p, ...a) => p === '/run/linux-studio/link-token' ? realRead(keyFile, ...a) : realRead(p, ...a);
const opened = []; const warnings = [];
Module._load = (req, ...a) => req === 'vscode' ? {
  window: { registerUriHandler: (h) => (global.h = h), showWarningMessage: (m) => warnings.push(m) },
  commands: { executeCommand: async (c, u) => opened.push(u) } } : orig(req, ...a);
const ext = require(routerPath); ext.activate({ subscriptions: [] });
const key = realRead(keyFile, 'utf8').trim();
const b64 = (s) => Buffer.from(s).toString('base64url');
let fail = 0;
const expect = (what, cond) => { if (!cond) fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${what}`); };
(async () => {
  const send = async (query, path = '/open') => { opened.length = 0; await global.h.handleUri({ path, query }); return opened.slice(); };
  // The editor gives the router an already-decoded query, so a link must survive that untouched.
  const tricky = 'https://example.com/cb?redirect_uri=https%3A%2F%2Fx.y%2F&state=a+b&scope=1';
  expect('Router: opens a tricky link exactly as sent (& + %2F kept)', JSON.stringify(await send(`u=${b64(tricky)}&k=${key}`)) === JSON.stringify([tricky]));
  expect('Router: ignores requests without the session key', (await send(`u=${b64('https://example.com/a')}`)).length === 0);
  expect('Router: ignores a wrong session key', (await send(`u=${b64('https://example.com/b')}&k=${'0'.repeat(64)}`)).length === 0);
  expect('Router: ignores file: links', (await send(`u=${b64('file:///etc/passwd')}&k=${key}`)).length === 0);
  expect('Router: ignores javascript: links', (await send(`u=${b64('javascript:alert(1)')}&k=${key}`)).length === 0);
  expect('Router: ignores user:password@ links', (await send(`u=${b64('https://good.com@evil.com/')}&k=${key}`)).length === 0);
  expect('Router: ignores other paths', (await send(`u=${b64('https://example.com/c')}&k=${key}`, '/other')).length === 0);
  // Rate limit: at most 3 per 10 s, same link within 2 s ignored, one warning.
  const lim = ext._test.makeLimiter(((t) => () => t)(1e6));
  const r = ['a', 'a', 'b', 'c', 'd', 'e'].map((l) => lim('https://' + l + '.example/'));
  expect('Router: same link twice within 2 s is ignored', r[1] === 'repeat');
  expect('Router: a 4th link within 10 s is stopped with one warning, then quietly', r[4] === 'limit-warn' && r[5] === 'limit');
  // The browser patch's rule (taken from the patch file itself).
  const patch = realRead(patchPath, 'utf8');
  const m = patch.match(/^\+.*?(\/\^linux-studio.*\/i)\.test/m);
  const re = eval(m[1]);
  const allow = (url, main = true) => main === true && re.test(url);
  expect('Browser patch: allows a sign-in callback from the page', allow('linux-studio://saoudrizwan.claude-dev/auth?code=1'));
  expect('Browser patch: refuses callbacks from frames inside the page', !allow('linux-studio://pub.ext/cb', false) && /isMainFrame === true/.test(patch));
  expect('Browser patch: refuses Linux Studio\'s own router', !allow('linux-studio://linux-studio.link-router/open?u=x') && !allow('LINUX-STUDIO://Linux-Studio.Link-Router?x'));
  expect('Browser patch: refuses other forms (file, no publisher)', !allow('linux-studio://file/etc/passwd') && !allow('linux-studio://ext') && !allow('vscode://pub.ext/x'));
  process.exit(fail ? 1 : 0);
})();
JS
out="$(node "$T/check.cjs" "$ROOT/src/editor/link-router/extension.js" "$T/key" "$ROOT/src/editor/patches/browser-callbacks.patch")"; echo "$out"
pass=$((pass + $(grep -c '^PASS' <<<"$out"))); fail=$((fail + $(grep -c '^FAIL' <<<"$out")))
echo; echo "$pass passed, $fail failed"; (( fail == 0 ))

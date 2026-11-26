#!/usr/bin/env bash
# Tests Linux Studio's extension signature checker (src/editor/vsce-sign) against real Open VSX files:
# a good extension passes; tampered, wrong, missing and broken signatures are refused with the right code.
# Needs: node (18+), curl, python3, openssl. Downloads one small extension (EditorConfig, ~250 KB) from open-vsx.org.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cd "$T"
read -r VSIX SIG < <(curl -sSf https://open-vsx.org/api/EditorConfig/EditorConfig | python3 -I -c \
  "import json,sys;f=json.load(sys.stdin)['files'];print(f['download'],f['signature'])")
curl -sSfL -o good.vsix "$VSIX"; curl -sSfL -o good.sigzip "$SIG"
cp good.vsix tampered.vsix; printf '\x00' | dd of=tampered.vsix bs=1 seek=1000 conv=notrunc 2>/dev/null
head -c 1000 /dev/urandom > notzip.sigzip
truncate -s 70M big.vsix
python3 -I - <<'PY'
import zipfile
z = zipfile.ZipFile('good.sigzip')
def mk(name, drop=(), patch={}):
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as o:
        for i in z.infolist():
            if i.filename not in drop:
                o.writestr(i.filename, patch.get(i.filename, z.read(i.filename)))
mk('nosig.sigzip', drop=('.signature.sig',))
mk('nomanifest.sigzip', drop=('.signature.manifest',))
mk('badsig.sigzip', patch={'.signature.sig': bytes(64)})
mk('shortsig.sigzip', patch={'.signature.sig': b'abc'})
mk('badmanifest.sigzip', patch={'.signature.manifest': b'{"package":{}}'})
mk('bomb.sigzip', patch={'.signature.manifest': b'{' + b' ' * (20 * 1024 * 1024) + b'}'})   # tiny when packed, 20 MB unpacked
mk('longsig.sigzip', patch={'.signature.sig': bytes(65)})
with zipfile.ZipFile('extra.sigzip', 'w', zipfile.ZIP_DEFLATED) as o:   # a big entry nobody needs must be skipped
    for i in z.infolist(): o.writestr(i.filename, z.read(i.filename))
    o.writestr('junk.bin', bytes(30 * 1024 * 1024))
with zipfile.ZipFile('many.sigzip', 'w') as o:
    for n in range(20): o.writestr(f'f{n}', b'x')
PY
cat > t.mjs <<'JS'
const { verify } = await import(process.argv[2]);
const cases = [
  ['good.vsix', 'good.sigzip', 'Success', 'a genuine Open VSX extension passes'],
  ['tampered.vsix', 'good.sigzip', 'PackageIntegrityCheckFailed', 'one changed byte is refused'],
  ['good.vsix', 'badsig.sigzip', 'SignatureIsNotValid', 'a forged signature is refused'],
  ['good.vsix', 'nosig.sigzip', 'SignatureIsMissing', 'a missing signature is refused'],
  ['good.vsix', 'nomanifest.sigzip', 'SignatureManifestIsMissing', 'a missing manifest is refused'],
  ['good.vsix', 'badmanifest.sigzip', 'SignatureManifestIsInvalid', 'a manifest without size/hash is refused'],
  ['good.vsix', 'shortsig.sigzip', 'SignatureIsInvalid', 'a malformed signature is refused'],
  ['good.vsix', 'notzip.sigzip', 'SignatureIsUnreadable', 'a broken signature archive is refused'],
  ['good.vsix', 'many.sigzip', 'SignatureArchiveHasTooManyEntries', 'an overfilled archive is refused'],
  ['missing.vsix', 'good.sigzip', 'PackageIsUnreadable', 'a missing package is refused'],
  ['good.vsix', 'bomb.sigzip', 'SignatureIsUnreadable', 'a "zip bomb" manifest is refused without unpacking it all'],
  ['good.vsix', 'longsig.sigzip', 'SignatureIsUnreadable', 'a signature entry of the wrong size is refused'],
  ['good.vsix', 'extra.sigzip', 'Success', 'a big unneeded entry is skipped, not unpacked'],
  ['big.vsix', 'good.sigzip', 'PackageIsUnreadable', 'a package over the size limit (set to 64 MB here) is refused'],
  ['good.vsix', '', 'RequiredArgumentMissing', 'a missing argument is refused'],
];
let pass = 0, fail = 0;
for (const [v, s, want, what] of cases) {
  const r = await verify(v, s, false);
  if (r.code === want && r.didExecute === true) { pass++; console.log(`PASS  ${what}`); }
  else { fail++; console.log(`FAIL  ${what} (got ${r.code}: ${r.output})`); }
}
console.log(`\n${pass} passed, ${fail} failed`); process.exit(fail ? 1 : 0);
JS
LS_MAX_EXTENSION_MB=64 node t.mjs "$ROOT/src/editor/vsce-sign/index.js"

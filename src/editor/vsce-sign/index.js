// Linux Studio extension signature checker.
//
// The editor (Code - OSS) checks every extension download by loading a module named "@vscode/vsce-sign" and calling
// verify(vsixPath, signatureArchivePath, verbose). Microsoft's own module is closed source and isn't part of Code - OSS,
// so without a replacement the check never runs. This file is that replacement, written for Open VSX:
//
//   1. Open the signature archive (.sigzip) that Open VSX publishes next to every extension. It holds
//      .signature.sig (a 64-byte Ed25519 signature) and .signature.manifest (size and SHA-256 of the package).
//   2. Check that the downloaded package's size and SHA-256 match the manifest.
//   3. Check the Ed25519 signature over the package's exact bytes against Open VSX's public key, which is pinned
//      below (never downloaded at install time, so a tampered server can't hand us its own key).
//
// Any problem returns a non-"Success" code. The editor then refuses the install and shows its prompt with
// "Install Anyway" (Project Manager decision 2026-11-26). Node built-ins only: no network, no telemetry.

import { createHash, createPublicKey, verify as edVerify } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { open } from 'node:fs/promises';
import { inflateRawSync } from 'node:zlib';

// Open VSX signing key, id 14ccb407-4e79-41ed-be5a-6d608325c45a, from https://open-vsx.org/api/-/public-key/<id>.
// SHA-256 of the key (DER): ffd108d00f4dac32e52b358a3452e15fe09815607b9d74d7ea39a3db49d4b623
// Checked 2026-11-26: the same key id is referenced by every extension sampled (Anthropic, Red Hat, Microsoft,
// rust-lang, golang, EditorConfig, including versions from 2020), and real signatures verify with it.
// If Open VSX ever changes its key, add the new one here (keep the old one while older versions still use it).
const PINNED_KEYS = [
  {
    id: '14ccb407-4e79-41ed-be5a-6d608325c45a',
    pem: '-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAje+vAaSS1zHV5WHCJSa5UXvxRo6+yerEU3IEmtuEuF4=\n-----END PUBLIC KEY-----\n',
  },
];

// Limits keep a hostile download from exhausting memory (security review 2026-11-26, findings 3 and 4).
// The whole package must be in memory to check an Ed25519 signature, so its size is capped. The cap is the Settings
// choice "Largest extension to check", 512 MB by default, 64 MB to 1.5 GB. The launcher puts it in a read-only file
// that code inside Linux Studio can't change; LS_MAX_EXTENSION_MB is only used when that file is absent (tests).
const LIMIT_FILE = '/run/linux-studio/max-extension-mb';
function maxPackageBytes() {
  let raw = process.env.LS_MAX_EXTENSION_MB ?? '';
  try { raw = readFileSync(LIMIT_FILE, 'utf8').trim(); } catch { /* not running under the launcher */ }
  const mb = Number.parseInt(raw, 10);
  const clamped = Number.isFinite(mb) ? Math.min(Math.max(mb, 64), 1536) : 512;
  return clamped * 1024 * 1024;
}
const MAX_ARCHIVE = 16 * 1024 * 1024;     // signature archive
const MAX_MANIFEST = 8 * 1024 * 1024;     // unpacked manifest (it lists every file, so big packages have big manifests)
const SIG_SIZE = 64;                      // Ed25519 signature
const MAX_ENTRIES = 16;
const NEEDED = { '.signature.sig': SIG_SIZE, '.signature.manifest': MAX_MANIFEST };   // the only entries ever unpacked

const C = {
  Success: 'Success',
  RequiredArgumentMissing: 'RequiredArgumentMissing',
  PackageIsUnreadable: 'PackageIsUnreadable',
  SignatureArchiveIsUnreadable: 'SignatureArchiveIsUnreadable',
  SignatureIsUnreadable: 'SignatureIsUnreadable',
  SignatureArchiveHasTooManyEntries: 'SignatureArchiveHasTooManyEntries',
  SignatureManifestIsMissing: 'SignatureManifestIsMissing',
  SignatureManifestIsInvalid: 'SignatureManifestIsInvalid',
  SignatureIsMissing: 'SignatureIsMissing',
  SignatureIsInvalid: 'SignatureIsInvalid',
  PackageIntegrityCheckFailed: 'PackageIntegrityCheckFailed',
  SignatureIsNotValid: 'SignatureIsNotValid',
  UnknownError: 'UnknownError',
};

class CheckError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

// Minimal ZIP reader for the small signature archive: central directory, then each entry (stored or deflated).
function readZip(buf) {
  const bad = (why) => { throw new CheckError(C.SignatureIsUnreadable, `signature archive: ${why}`); };
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 65535); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) bad('not a ZIP file');
  const count = buf.readUInt16LE(eocd + 10);
  const cdSize = buf.readUInt32LE(eocd + 12);
  const cdOffset = buf.readUInt32LE(eocd + 16);
  if (count > MAX_ENTRIES) throw new CheckError(C.SignatureArchiveHasTooManyEntries, `signature archive has ${count} entries`);
  if (cdOffset + cdSize > eocd) bad('central directory out of range');
  const entries = new Map();
  const seen = new Set();
  let p = cdOffset;
  for (let n = 0; n < count; n++) {
    if (p + 46 > eocd || buf.readUInt32LE(p) !== 0x02014b50) bad('broken central directory');
    const flags = buf.readUInt16LE(p + 8);
    const method = buf.readUInt16LE(p + 10);
    const csize = buf.readUInt32LE(p + 20);
    const usize = buf.readUInt32LE(p + 24);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString('utf8', p + 46, p + 46 + nameLen);
    p += 46 + nameLen + extraLen + commentLen;
    if (flags & 0x1) bad('encrypted entry');
    if (seen.has(name)) bad(`duplicate entry ${name}`);
    seen.add(name);
    if (!(name in NEEDED)) continue;   // other entries (e.g. the empty .signature.p7s) are never unpacked
    if (usize > NEEDED[name] || csize > MAX_ARCHIVE) bad(`entry ${name} too large`);
    if (local + 30 > buf.length || buf.readUInt32LE(local) !== 0x04034b50) bad(`broken local header for ${name}`);
    const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
    if (start + csize > buf.length) bad(`entry ${name} out of range`);
    const raw = buf.subarray(start, start + csize);
    let data;
    if (method === 0) data = Buffer.from(raw);
    else if (method === 8) {
      try { data = inflateRawSync(raw, { maxOutputLength: NEEDED[name] }); } catch { bad(`can't unpack ${name}`); }
    } else bad(`unsupported compression in ${name}`);
    if (data.length !== usize) bad(`entry ${name} has the wrong size`);
    entries.set(name, data);
  }
  return entries;
}

function check(pkg, archive) {
  const entries = readZip(archive);
  const sig = entries.get('.signature.sig');
  const manifestRaw = entries.get('.signature.manifest');
  if (!manifestRaw) throw new CheckError(C.SignatureManifestIsMissing, 'no .signature.manifest in the signature archive');
  if (!sig || sig.length === 0) throw new CheckError(C.SignatureIsMissing, 'no .signature.sig in the signature archive');
  if (sig.length !== SIG_SIZE) throw new CheckError(C.SignatureIsInvalid, `signature is ${sig.length} bytes, expected 64 (Ed25519)`);

  let manifest;
  try { manifest = JSON.parse(manifestRaw.toString('utf8')); } catch { manifest = null; }
  const expectSize = manifest?.package?.size;
  const expectSha = manifest?.package?.digests?.sha256;
  if (!Number.isSafeInteger(expectSize) || typeof expectSha !== 'string') {
    throw new CheckError(C.SignatureManifestIsInvalid, 'signature manifest has no package size or SHA-256');
  }
  if (pkg.length !== expectSize) {
    throw new CheckError(C.PackageIntegrityCheckFailed, `package is ${pkg.length} bytes, the manifest says ${expectSize}`);
  }
  const sha = createHash('sha256').update(pkg).digest('base64');
  if (sha !== expectSha) throw new CheckError(C.PackageIntegrityCheckFailed, 'package SHA-256 does not match the manifest');

  for (const k of PINNED_KEYS) {
    if (edVerify(null, pkg, createPublicKey(k.pem), sig)) return `signature valid (Open VSX key ${k.id})`;
  }
  throw new CheckError(C.SignatureIsNotValid, 'signature does not match the package with any pinned Open VSX key');
}

// Reads at most `max` bytes through one open file handle, so a file that grows after the size check is still caught.
async function readLimited(path, max, unreadableCode, what) {
  let fh;
  try {
    fh = await open(path, 'r');
    const s = await fh.stat();
    if (!s.isFile()) throw new Error('not a file');
    if (s.size > max) throw new Error(`larger than the ${Math.round(max / 1048576)} MB limit`);
    const buf = Buffer.alloc(s.size + 1);
    let got = 0;
    while (got < buf.length) {
      const { bytesRead } = await fh.read(buf, got, buf.length - got, got);
      if (bytesRead === 0) break;
      got += bytesRead;
    }
    if (got > s.size) throw new Error('file changed while being read');
    return buf.subarray(0, got);
  } catch (e) {
    throw new CheckError(unreadableCode, `${what} unreadable: ${e.message}`);
  } finally {
    await fh?.close();
  }
}

export async function verify(vsixFilePath, signatureArchiveFilePath, verbose) {
  if (!vsixFilePath || !signatureArchiveFilePath) {
    return { code: C.RequiredArgumentMissing, didExecute: true, output: 'package or signature archive path missing' };
  }
  try {
    const pkg = await readLimited(vsixFilePath, maxPackageBytes(), C.PackageIsUnreadable, 'package');
    const archive = await readLimited(signatureArchiveFilePath, MAX_ARCHIVE, C.SignatureArchiveIsUnreadable, 'signature archive');
    const output = check(pkg, archive);
    return { code: C.Success, didExecute: true, output: verbose ? `Linux Studio signature check: ${output}` : output };
  } catch (e) {
    const code = e instanceof CheckError ? e.code : C.UnknownError;
    return { code, didExecute: true, output: `Linux Studio signature check: ${e.message}` };
  }
}

export default { verify };

// Linux Studio link router (built-in extension).
// Linux Studio's xdg-open (inside the sandbox) sends web links here as
//   linux-studio://linux-studio.link-router/open?u=<base64url of the http(s) link>&k=<this session's key>
// and this opens them in a tab inside Linux Studio (the editor's Integrated Browser).
//
// Security review 2026-11-26:
//   F1  the link is base64url-encoded, so the editor's own decoding can't change or truncate it;
//   F2  only requests carrying this session's key (from a read-only file only Linux Studio's xdg-open reads) are
//       accepted, so web pages can't drive the router; and at most 3 links open per 10 seconds (PM decision), with the
//       same link repeated within 2 seconds ignored.
// Only http and https links are opened. No network access of its own, no telemetry.
'use strict';
const vscode = require('vscode');
const fs = require('fs');
const crypto = require('crypto');

const KEY_FILE = '/run/linux-studio/link-token';
const MAX_LENGTH = 8192;
const RATE_MAX = 3;            // links ...
const RATE_WINDOW_MS = 10000;  // ... per 10 seconds
const REPEAT_MS = 2000;        // the same link again within 2 s is ignored

function webLink(raw) {
  if (typeof raw !== 'string' || raw.length === 0 || raw.length > MAX_LENGTH) return undefined;
  let u;
  try { u = new URL(raw); } catch { return undefined; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return undefined;
  if (u.username || u.password) return undefined;   // no "user:password@" links (often used to disguise a site)
  return u.toString();
}

function decodeLink(b64) {
  if (typeof b64 !== 'string' || !/^[A-Za-z0-9_-]{1,11000}$/.test(b64)) return undefined;
  try { return Buffer.from(b64, 'base64url').toString('utf8'); } catch { return undefined; }
}

function sessionKey() {
  try {
    const k = fs.readFileSync(KEY_FILE, 'utf8').trim();
    return /^[a-f0-9]{64}$/.test(k) ? k : undefined;
  } catch { return undefined; }
}

function sameKey(given, expected) {
  if (typeof given !== 'string' || !expected || given.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(expected));
}

function makeLimiter(now = () => Date.now()) {
  const opened = [];   // [time, link]
  let warned = 0;
  return (link) => {
    const t = now();
    while (opened.length && t - opened[0][0] > RATE_WINDOW_MS) opened.shift();
    if (opened.some(([ot, ol]) => ol === link && t - ot < REPEAT_MS)) return 'repeat';
    if (opened.length >= RATE_MAX) {
      if (t - warned > RATE_WINDOW_MS) { warned = t; return 'limit-warn'; }
      return 'limit';
    }
    opened.push([t, link]);
    return 'ok';
  };
}

// Parses the router's own query. The editor hands us an already-decoded query string; the values we use are plain
// base64url and hex, so they are the same before and after decoding.
function parseQuery(query) {
  const out = {};
  for (const part of String(query || '').split('&')) {
    const i = part.indexOf('=');
    if (i > 0) out[part.slice(0, i)] = part.slice(i + 1);
  }
  return out;
}

exports.activate = (context) => {
  const key = sessionKey();
  const limit = makeLimiter();
  context.subscriptions.push(vscode.window.registerUriHandler({
    async handleUri(uri) {
      if (uri.path !== '/open') return;
      const q = parseQuery(uri.query);
      if (!sameKey(q.k, key)) return;                       // not from Linux Studio's own xdg-open
      const link = webLink(decodeLink(q.u));
      if (!link) return;
      const verdict = limit(link);
      if (verdict === 'repeat' || verdict === 'limit') return;
      if (verdict === 'limit-warn') {
        vscode.window.showWarningMessage('Linux Studio stopped opening more links for a few seconds (at most 3 every 10 seconds).');
        return;
      }
      try {
        await vscode.commands.executeCommand('workbench.action.browser.open', link);
      } catch {
        vscode.window.showWarningMessage(`Linux Studio couldn't open ${link} in a tab.`);
      }
    }
  }));
};

exports.deactivate = () => {};
exports._test = { webLink, decodeLink, sameKey, makeLimiter, parseQuery };

// Linux Studio network inbox status (built-in extension, approved mockup screen 8).
// Shows "🌐 N waiting" at the right of the status bar while websites wait for approval in Linux Studio's network
// inbox, and asks Linux Studio to open the inbox when clicked. It runs inside the sandbox, so it can only:
//   * read the waiting count from a read-only file Linux Studio provides (/run/linux-studio/status/pending), and
//   * send one fixed "open the inbox" request through the proxy (rate-limited by the proxy).
// It can't see which sites are waiting and can't answer anything: answers happen in the inbox window on your desktop.
// No network access of its own, no telemetry.
'use strict';
const vscode = require('vscode');
const fs = require('fs');
const net = require('net');

const COUNT_FILE = '/run/linux-studio/status/pending';
const POLL_MS = 2000;

function readCount() {
  try {
    const n = Number.parseInt(fs.readFileSync(COUNT_FILE, 'utf8').trim(), 10);
    return Number.isFinite(n) && n > 0 ? Math.min(n, 999) : 0;
  } catch {
    return 0;
  }
}

function askForInbox() {
  // The in-sandbox proxy bridge passes this to Linux Studio's proxy outside, which opens the inbox window.
  const sock = net.connect({ host: '127.0.0.1', port: 3128 }, () => sock.end('LINUX-STUDIO-INBOX open\r\n\r\n'));
  sock.setTimeout(5000, () => sock.destroy());
  sock.on('error', () => { /* proxy not reachable: nothing to do */ });
  sock.on('data', () => sock.destroy());
}

exports.activate = (context) => {
  const item = vscode.window.createStatusBarItem('linuxStudio.networkInbox', vscode.StatusBarAlignment.Right, 1000);
  item.name = 'Linux Studio network inbox';
  item.command = 'linuxStudio.openNetworkInbox';
  item.tooltip = 'Websites waiting for your approval: click to open the Network inbox';
  context.subscriptions.push(item, vscode.commands.registerCommand('linuxStudio.openNetworkInbox', askForInbox));
  let shown = -1;
  const refresh = () => {
    const n = readCount();
    if (n === shown) return;
    shown = n;
    if (n > 0) {
      item.text = `$(globe) ${n} waiting`;
      item.show();
    } else {
      item.hide();
    }
  };
  refresh();
  const timer = setInterval(refresh, POLL_MS);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });
};

exports.deactivate = () => {};

#!/usr/bin/python3
"""One-time private download link for a single file (used to hand a dev build to the Project Manager).

It listens on 127.0.0.1 only (in a Codespace, reach it through the editor's PRIVATE port forward, which requires your
GitHub sign-in), serves the file only at a random, unguessable address, and shuts itself down after ONE complete
download or after TIMEOUT seconds, whichever comes first, so no port is left open (guidelines/Security.md:
"never leave ports open"). An interrupted download keeps the link open so it can be retried.

Usage:   scripts/serve-once.py FILE [PORT] [TIMEOUT]      (defaults: port 8765, 1800 seconds)
Prints:  READY path=/<random>   - the link is https://<codespace>-<PORT>.app.github.dev/<random>
Standard library only.
"""
import http.server
import os
import secrets
import sys
import threading


def main():
    if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
        print(__doc__, file=sys.stderr)
        return 2
    path = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 1800
    name = os.path.basename(path)
    token = secrets.token_urlsafe(16)
    size = os.path.getsize(path)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass   # no access log

        def do_GET(self):
            if self.path == f"/{token}":
                page = (f'<p><a href="/{token}/{name}">Download {name}</a> ({size // 1048576} MB)</p>'
                        '<p>This link stops working after one complete download.</p>').encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            if self.path != f"/{token}/{name}":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(size))
            self.end_headers()
            sent = 0
            try:
                with open(path, "rb") as f:
                    while chunk := f.read(1 << 20):
                        self.wfile.write(chunk)
                        sent += len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                print(f"Download interrupted at {sent // 1048576} MB; link still open.", flush=True)
                return
            print("Download complete; closing.", flush=True)
            threading.Thread(target=server.shutdown).start()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Timer(timeout, server.shutdown).start()
    print(f"READY path=/{token}", flush=True)
    server.serve_forever()
    server.server_close()
    print("Server closed.", flush=True)
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())

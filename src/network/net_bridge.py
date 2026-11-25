#!/usr/bin/env python3
"""Runs INSIDE the sandbox. Gives programs a normal proxy address (127.0.0.1:3128) and passes each
connection to the Linux Studio proxy through the socket at /run/linux-studio/proxy.sock.
It makes no decisions itself; the proxy outside decides everything.

It starts listening, then moves to the background so the editor or shell can start right after.
Standard library only.
"""
import os
import select
import socket
import sys
import threading

LISTEN = ("127.0.0.1", 3128)
PROXY_SOCKET = "/run/linux-studio/proxy.sock"


def pipe(a, b):
    try:
        while True:
            ready, _, _ = select.select([a, b], [], [], 600)
            if not ready:
                return
            for s in ready:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except OSError:
        pass
    finally:
        a.close()
        b.close()


def serve(listener):
    while True:
        client, _ = listener.accept()
        try:
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(PROXY_SOCKET)
        except OSError:
            client.close()
            continue
        threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()


def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(LISTEN)
    listener.listen(128)
    if os.fork() > 0:          # parent returns once the port is ready
        os._exit(0)
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    serve(listener)


if __name__ == "__main__":
    sys.exit(main())

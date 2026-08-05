#!/usr/bin/env python3
"""Small adapter around the separately installed Freenove server code."""
from __future__ import annotations

import argparse
import json
import os
import socketserver
import sys
from pathlib import Path


def load_control(server_dir: Path):
    sys.path.insert(0, str(server_dir))
    from control import Control  # type: ignore

    return Control()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            try:
                if method == "status":
                    result = {"connected": True, "socket": self.server.server_address}
                else:
                    target = getattr(self.server.device, method)
                    if method.startswith("_") or not callable(target):
                        raise AttributeError(method)
                    result = target(*request.get("args", []), **request.get("kwargs", {}))
                response = {"id": request_id, "ok": True, "result": result}
            except Exception as exc:
                response = {"id": request_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.wfile.write(json.dumps(response, default=repr).encode() + b"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--server-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    with socketserver.ThreadingUnixStreamServer(args.socket, Handler) as server:
        server.device = load_control(args.server_dir)
        server.serve_forever()


if __name__ == "__main__":
    main()


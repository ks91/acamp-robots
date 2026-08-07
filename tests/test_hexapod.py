import json
import os
import socket
import threading

from acamp_robots.controller import HexapodController


def test_turn_by_uses_timeout_longer_than_two_server_segments(monkeypatch):
    observed = {}

    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): observed["timeout"] = value
        def connect(self, path): pass
        def sendall(self, payload): pass
        def recv(self, size): return b'{"id":1,"ok":true,"result":{}}\n'

    monkeypatch.setattr(socket, "socket", lambda *args: FakeSocket())
    HexapodController("/tmp/test.sock", timeout=5).call("turn_by", "clockwise", 360)
    assert observed["timeout"] == 15


def test_rpc_call_uses_newline_json_protocol(tmp_path):
    # macOS limits AF_UNIX paths to about 100 bytes; pytest's tmp path can exceed it.
    path = f"/tmp/acamp-rpc-test-{os.getpid()}.sock"
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    received = {}

    def serve():
        connection, _ = server.accept()
        with connection:
            received.update(json.loads(connection.recv(4096)))
            connection.sendall(b'{"id":1,"ok":true,"result":"done"}\n')
        server.close()

    thread = threading.Thread(target=serve)
    thread.start()
    result = HexapodController(path).call("move", 1, x=2)
    thread.join()
    os.unlink(path)

    assert result == "done"
    assert received["method"] == "move"
    assert received["args"] == [1]
    assert received["kwargs"] == {"x": 2}

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .controller import HexapodController, create_controller


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="アカデミーキャンプ ロボット制御 CLI")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="設定または RPC の状態を表示")
    call = subparsers.add_parser("call", help="ロボットのメソッドを呼ぶ")
    call.add_argument("method")
    call.add_argument("args", nargs="*", help="JSON として解釈する引数")
    ns = parser.parse_args(argv)
    config = load_config(ns.root)
    controller = create_controller(config, ns.root)

    if ns.command == "status":
        result = controller.status() if isinstance(controller, HexapodController) else {"robot": "arm", "ready": True}
    else:
        args = [json.loads(value) for value in ns.args]
        if ns.method.startswith("_"):
            parser.error("_ で始まるメソッドは呼べません")
        target = getattr(controller, ns.method, None)
        result = target(*args) if callable(target) else controller.call(ns.method, *args)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


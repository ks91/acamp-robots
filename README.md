# Academy Camp Robots

サイエンスキャンプ「アカデミーキャンプ」で、コーディング・エージェントからロボットを動かすための小さな制御環境です。音声機能、01、LiveKit は使いません。

対応機種は次の2種類です。

- Yahboom DOFBOT ロボットアーム
- Freenove Big Hexapod Robot Kit

## Raspberry Pi への準備

この public リポジトリを Raspberry Pi に clone し、使う機種を一度だけ選びます。

```bash
git clone <このリポジトリのURL> acamp-robots
cd acamp-robots
./scripts/setup.sh --robot arm       # DOFBOT
# または
./scripts/setup.sh --robot hexapod  # Freenove
```

設定は `.acamp-robot.json` に保存されます。このファイルは Raspberry Pi ごとの設定なので Git には入りません。機種を変えるときは setup をもう一度実行します。

## ベンダー提供ソフトウェアの置き場所

このリポジトリはベンダーのハードウェア制御コードを再配布しません。

### DOFBOT

DOFBOT に付属する `Arm_Lib.py` を次の場所に置いてください。

```text
hardware/Arm_Lib.py
```

`Arm_Lib.py` はライセンスが明確でないため、このリポジトリには含めず `.gitignore` でも除外しています。DOFBOT の公式イメージやメーカー提供物から、各 Raspberry Pi に直接コピーしてください。

### Freenove Hexapod

Freenove の Raspberry Pi 用 Server 一式が、標準では次の配置になるようにします。

```text
hardware/freenove/Code/Server/main.py
hardware/freenove/Code/Server/control.py
...
```

別の場所を使う場合は `HEXAPOD_SERVER_DIR` を指定できます。Freenove の配布物には独自のライセンス条件があるため、その `LICENSE.txt` を確認して従ってください。

## セッションを始める

SSH で Raspberry Pi に入り、次を実行します。

```bash
./scripts/start-agent.sh
```

このスクリプトは機種に合わせた準備をしてから `loglm -X` を起動します。

- DOFBOT: 実行中の Docker コンテナを停止し、カメラを解放します。処理は毎回安全に再実行できるので、電源投入後の最初のセッションで確実に行われます。
- Hexapod: ローカル Unix ソケットの RPC ブリッジを、まだ動いていない場合だけ起動します。

`-X` はエージェントの実行確認を省略します。参加者の体験を止めないための運用ですが、Raspberry Pi には秘密情報や不要な認証情報を置かず、ロボットの周囲を片づけ、非常停止できる大人が見守ってください。

`loglm` が PATH にない場合は指定できます。

```bash
LOGLM_BIN=../loglm/loglm ./scripts/start-agent.sh
```

## Python から制御する

```python
from pathlib import Path
from acamp_robots import create_controller, load_config

root = Path.cwd()
robot = create_controller(load_config(root), root)
```

DOFBOT の例:

```python
robot.move_joints([90, 90, 90, 90, 90, 30], duration_ms=1000)
```

Hexapod の例（`move`, `stop`, `speed`, `balance`, `position`, `attitude`, `head_vertical`, `head_horizontal`, `servopower` を RPC で呼べます）:

```python
robot.call("stop")
robot.call("move", 1, 5, 0, 0)
```

CLI でも確認できます。

```bash
.venv/bin/acamp-robot status
.venv/bin/acamp-robot call stop
```

## 開発とテスト

実機は不要です。

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

テストでは外部 `Arm_Lib.py` と Unix ソケット RPC を偽物に差し替えます。実機で試す前に、机上で制御ロジックを検証できます。

## 安全

- アームや脚の可動範囲に、顔、指、ケーブルを入れないでください。
- 最初は低速・小さい動きで試してください。
- 異常時はロボットの電源を切れる状態で実験してください。
- `scripts/stop-camera-containers.sh` は実行中の全 Docker コンテナを止めます。ロボット専用 Raspberry Pi でだけ使ってください。

#!/usr/bin/env python3
import subprocess
import threading
import time
import sys
import logging
import os

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PORT = 8000


def run_uvicorn():
    """node.py をFastAPIサーバとして起動"""
    logger.info("FastAPIサーバを起動しています...")
    try:
        if os.path.exists("node.py"):
            subprocess.run(
                ["uvicorn", "node:app", "--host", "0.0.0.0", "--port", str(PORT)]
            )
        else:
            logger.error(
                "node.py が見つかりません。同じディレクトリに配置してください。"
            )
            sys.exit(1)
    except Exception as e:
        logger.error(f"FastAPIサーバ起動エラー: {e}")
        sys.exit(1)


def run_mine_loop():
    """mine_loop.py を実行"""
    logger.info("マイニングループを開始しています...")
    try:
        subprocess.run([sys.executable, "mine_loop.py"])
    except Exception as e:
        logger.error(f"マイニングループエラー: {e}")


def run_sync_loop():
    """sync_loop.py を実行"""
    logger.info("同期ループを開始しています...")
    try:
        subprocess.run([sys.executable, "sync_loop.py"])
    except Exception as e:
        logger.error(f"同期ループエラー: {e}")


if __name__ == "__main__":
    logger.info("ブロックチェーンノードを起動します")

    # 必要なファイルの存在チェック
    required_files = ["node.py", "mine_loop.py", "sync_loop.py"]
    missing_files = [f for f in required_files if not os.path.exists(f)]

    if missing_files:
        logger.error(f"以下のファイルが見つかりません: {', '.join(missing_files)}")
        logger.error(
            "すべてのファイルが同じディレクトリに配置されていることを確認してください。"
        )
        sys.exit(1)

    # FastAPIサーバをバックグラウンドスレッドで起動
    t1 = threading.Thread(target=run_uvicorn, daemon=True)
    t1.start()

    # サーバー起動待機
    logger.info("FastAPIサーバの起動を待機しています...")
    time.sleep(5)

    logger.info("ブロックチェーンノードが起動しました")

    # マイニングと同期も別スレッドで起動
    t2 = threading.Thread(target=run_mine_loop, daemon=True)
    t3 = threading.Thread(target=run_sync_loop, daemon=True)
    t2.start()
    t3.start()

    # メインスレッドを待機状態に
    try:
        logger.info("Ctrl+Cで終了します")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("終了します")

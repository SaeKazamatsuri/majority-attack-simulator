#!/usr/bin/env python3
import requests
import time
import logging
import socket
import random
import os
import json

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# 設定ファイルからノードURLを取得するか、デフォルトを使用
def get_node_url():
    config_file = "node_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                ip = config.get("my_node_ip", "localhost")
                return f"http://{ip}:8000"
        except Exception as e:
            logger.error(f"設定ファイルの読み込みエラー: {e}")

    # デフォルト値
    return "http://localhost:8000"


NODE_URL = get_node_url()
MINE_INTERVAL = 5  # 採掘間隔（秒）


def mine_block():
    """ブロックを採掘する"""
    try:
        logger.info(f"ブロック採掘リクエスト: {NODE_URL}/mine")
        res = requests.post(f"{NODE_URL}/mine", timeout=10)
        if res.status_code == 200:
            data = res.json()
            logger.info(
                f"✅ ブロック採掘成功: インデックス={data.get('index')}, ハッシュ={data.get('hash')[:10]}..."
            )
            return True
        else:
            logger.error(f"❌ ブロック採掘失敗: ステータスコード {res.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"❌ 採掘リクエストエラー: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ 予期しないエラー: {e}")
        return False


if __name__ == "__main__":
    logger.info(f"マイニングループを開始: ノード={NODE_URL}, 間隔={MINE_INTERVAL}秒")

    # サーバーが起動するまで待機
    time.sleep(2)

    failures = 0
    max_failures = 5

    while True:
        success = mine_block()

        if not success:
            failures += 1
            if failures >= max_failures:
                logger.warning(f"連続{max_failures}回の失敗。短時間待機します...")
                time.sleep(30)  # より長い待機
                failures = 0
        else:
            failures = 0

        # ジッターを加えて一斉採掘を防止
        jitter = random.uniform(0, 1)
        wait_time = MINE_INTERVAL + jitter

        time.sleep(wait_time)

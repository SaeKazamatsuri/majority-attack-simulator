#!/usr/bin/env python3
import requests
import time
import logging
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

# ----------------------------------------
# クライアント設定
# ----------------------------------------
CONFIG_FILE = "node_config.json"
SYNC_INTERVAL = 30  # 同期間隔（秒）

# サーバーと同じ候補リストを持つ
PEERS_CANDIDATE = [
    "http://100.69.208.89:8000",
    "http://100.76.231.73:8000",
    "http://100.92.167.99:8000",
    "http://100.75.238.65:8000",
]


# 起動時に読み込む「自ノードURL」
def get_node_url():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                ip = json.load(f).get("my_node_ip", "localhost")
                return f"http://{ip}:8000"
        except Exception as e:
            logger.error(f"設定読み込みエラー: {e}")
    return "http://localhost:8000"


NODE_URL = get_node_url()

# 発見済みピアを保持する集合
peers = set()


# ----------------------------------------
# 自ノードを候補ノードに登録
# ----------------------------------------
def register_to_candidates():
    """起動時に候補ノード全てへ自ノードを /peers で登録"""
    for candidate in PEERS_CANDIDATE:
        if candidate == NODE_URL:
            continue
        try:
            res = requests.post(f"{candidate}/peers", json={"url": NODE_URL}, timeout=5)
            if res.status_code == 200:
                logger.info(f"✅ {candidate} に自ノード情報を登録")
            else:
                logger.warning(f"❌ {candidate} への登録失敗: HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"❌ {candidate} への登録エラー: {e}")


# ----------------------------------------
# ピア情報取得／更新
# ----------------------------------------
def check_peers():
    """
    候補リストと既存ピアを巡回し、
    各 /peers から返ってきたURLを peers にマージ
    """
    global peers
    # (1) 候補リストを巡回
    for url in PEERS_CANDIDATE + list(peers):
        try:
            res = requests.get(f"{url}/peers", timeout=5)
            if res.status_code == 200:
                data = res.json().get("peers", [])
                for p in data:
                    if p != NODE_URL:
                        peers.add(p)
                logger.info(f"✔ {url} のピアを取得: {len(data)} 件")
            else:
                logger.warning(f"✖ {url} のピア取得失敗: HTTP {res.status_code}")
        except Exception as e:
            logger.debug(f"--- {url} アクセス失敗: {e}")
    logger.info(f"▶ 現在のピア総数: {len(peers)} => {peers}")


# ----------------------------------------
# チェーン同期
# ----------------------------------------
def sync_chain():
    """
    自ノードと発見済みピア全てに対して /sync を順番に投げる
    """
    targets = {NODE_URL, *peers}
    for url in targets:
        try:
            logger.info(f"チェーン同期リクエスト: {url}/sync")
            res = requests.post(f"{url}/sync", timeout=10)
            if res.status_code == 200:
                data = res.json()
                status = data.get("status")
                length = data.get("length")
                logger.info(f"✓ [{url}] {status} → 長さ={length}")
            else:
                logger.warning(f"✖ [{url}] 同期失敗: HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"⚠ [{url}] 同期エラー: {e}")


# ----------------------------------------
# メインループ
# ----------------------------------------
if __name__ == "__main__":
    logger.info(f"クライアント起動: 自ノード={NODE_URL}")
    # 候補ノードへまず自ノードを登録
    register_to_candidates()

    # サーバー起動待ち
    time.sleep(3)

    failures = 0
    max_failures = 5

    while True:
        # (1) ピア情報取得
        check_peers()

        # (2) チェーン同期
        try:
            sync_chain()
            failures = 0
        except Exception:
            failures += 1
            if failures >= max_failures:
                logger.warning(f"❗︎ 連続失敗 {max_failures} 回。60秒待機します。")
                time.sleep(60)
                failures = 0

        # ジッター付き待機
        jitter = random.uniform(0, 2)
        time.sleep(SYNC_INTERVAL + jitter)

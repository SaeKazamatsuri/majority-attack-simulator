#!/usr/bin/env python3
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import time
import hashlib
import requests
import json
import os
import threading
import socket
import netifaces
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- ブロック定義 --------------------
class Block:
    def __init__(self, index, previous_hash, timestamp, data, difficulty):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.nonce = 0
        self.difficulty = difficulty
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = (
            f"{self.index}{self.previous_hash}{self.timestamp}{self.data}{self.nonce}"
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self):
        prefix = "0" * self.difficulty
        while not self.hash.startswith(prefix):
            self.nonce += 1
            self.hash = self.calculate_hash()
        logger.info(
            f"[MINED] index: {self.index}, hash: {self.hash}, nonce: {self.nonce}"
        )


# -------------------- グローバル変数 --------------------
difficulty = 4  # 難易度は4に設定（処理時間の短縮）
blockchain: List[Block] = []
peers: List[str] = []

CONFIG_FILE = "node_config.json"
PORT = 8000
MY_IP = None
MY_NODE = None

# 候補としての既知のノード
PEERS_CANDIDATE = [
    "http://100.69.208.89:8000",
    "http://100.76.231.73:8000",
    "http://100.92.167.99:8000",
    "http://100.75.238.65:8000",
    "http://localhost:8000",
]


# -------------------- ユーティリティ関数 --------------------
def load_node_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("my_node_ip")
        except Exception as e:
            logger.error(f"[設定エラー] {e}")
    return None


def get_all_ips():
    all_ips = []
    try:
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr["addr"]
                    if not ip.startswith("127."):
                        all_ips.append(ip)
        tailscale_ips = [ip for ip in all_ips if ip.startswith("100.")]
        return tailscale_ips or all_ips
    except Exception as e:
        logger.error(f"IP取得エラー: {e}")
        return ["127.0.0.1"]


def detect_my_ip():
    ip = load_node_config()
    if ip:
        return ip

    # ファイルがない場合はIPを検出
    try:
        # ローカルネットワーク内でのIP取得
        all_ips = get_all_ips()

        if not all_ips:
            ip = "127.0.0.1"
        elif len(all_ips) == 1:
            ip = all_ips[0]
        else:
            # Tailscaleを優先
            tailscale_ips = [ip for ip in all_ips if ip.startswith("100.")]
            if tailscale_ips:
                ip = tailscale_ips[0]
            else:
                # それ以外は最初のプライベートIPを使用
                private_ips = [
                    ip for ip in all_ips if ip.startswith(("192.168.", "10.", "172."))
                ]
                if private_ips:
                    ip = private_ips[0]
                else:
                    ip = all_ips[0]

        # 設定ファイルに保存
        with open(CONFIG_FILE, "w") as f:
            json.dump({"my_node_ip": ip}, f)
        logger.info(f"[保存] 自ノードIPを {ip} に設定")

        return ip
    except Exception as e:
        logger.error(f"IP検出エラー: {e}")
        return "127.0.0.1"


def add_peer_if_new(url: str):
    if url and url not in peers and url != MY_NODE:
        peers.append(url)
        logger.info(f"[PEER] 新規ノードを登録: {url}")
        return True
    return False


def sync_peers():
    """定期的に既知の候補と既存のピアから最新のノード情報を取得して登録する"""
    global peers
    all_known_urls = set(peers)  # 既存のピア情報

    # 候補リストから問い合わせ
    for candidate in PEERS_CANDIDATE:
        if candidate == MY_NODE:
            continue
        try:
            res = requests.get(f"{candidate}/peers", timeout=3)
            data = res.json()
            for url in data.get("peers", []):
                all_known_urls.add(url)
        except Exception as e:
            logger.warning(f"[WARN] 候補 {candidate} からの取得に失敗: {e}")

    # 既存ピアからも問い合わせ（双方向通信のため）
    for peer in list(peers):
        if peer == MY_NODE:
            continue
        try:
            res = requests.get(f"{peer}/peers", timeout=3)
            data = res.json()
            for url in data.get("peers", []):
                all_known_urls.add(url)
        except Exception as e:
            logger.warning(f"[WARN] ピア {peer} からの取得に失敗: {e}")

    # 登録されていないピアがあれば登録し、相手にも自ノード情報を送信
    for url in all_known_urls:
        if add_peer_if_new(url):
            try:
                requests.post(f"{url}/peers", json={"url": MY_NODE}, timeout=3)
                logger.info(f"[PEER] {url} に自ノード情報を送信")
            except Exception as e:
                logger.error(f"[ERROR] {url} への送信失敗: {e}")


def periodic_peer_sync(interval: int = 30):
    """
    一定間隔でピア情報を同期するスレッドを開始
    interval: 同期間隔（秒）
    """

    def worker():
        while True:
            sync_peers()
            time.sleep(interval)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def is_chain_valid(chain):
    """チェーンの整合性を検証する"""
    for i in range(1, len(chain)):
        current = chain[i]
        previous = chain[i - 1]

        # ハッシュ値の検証
        if current.previous_hash != previous.hash:
            return False

        # 現在のブロックのハッシュ値の検証
        if current.hash != current.calculate_hash():
            return False

        # 難易度に応じたハッシュ値の検証
        if not current.hash.startswith("0" * current.difficulty):
            return False

    return True


# -------------------- 初期化 --------------------
@app.on_event("startup")
def startup_event():
    global MY_IP, MY_NODE

    MY_IP = detect_my_ip()
    MY_NODE = f"http://{MY_IP}:{PORT}"
    logger.info(f"[起動] 自ノード: {MY_NODE}")

    # Genesisブロック作成
    if not blockchain:
        genesis = Block(0, "0", time.time(), "Genesis Block", difficulty)
        genesis.mine_block()
        blockchain.append(genesis)

    # バックグラウンドで定期的なピア同期を開始
    periodic_peer_sync(interval=30)  # 30秒周期で同期


# -------------------- チェーン取得 --------------------
@app.get("/chain")
def get_chain():
    return [vars(b) for b in blockchain]


# -------------------- マイニング --------------------
@app.post("/mine")
def mine_block(request: Request):
    client_ip = request.client.host
    logger.info(f"[MINE] リクエスト元IP: {client_ip}")

    # データ生成（通常のデータか攻撃データか）
    data = "normal"
    # 例として特定IPを攻撃用データとする（例示のため残しています）
    if client_ip == "100.75.238.65":
        data = "attack"

    # 新しいブロックの生成とマイニング
    last_block = blockchain[-1]
    new_block = Block(len(blockchain), last_block.hash, time.time(), data, difficulty)
    new_block.mine_block()
    blockchain.append(new_block)

    # 他のノードにブロードキャスト
    broadcast_new_block(new_block)

    return {
        "message": "New block mined",
        "index": new_block.index,
        "hash": new_block.hash,
        "by": client_ip,
    }


def broadcast_new_block(block):
    """新しいブロックを他のノードにブロードキャストする"""
    block_data = vars(block)
    for peer in peers:
        try:
            requests.post(f"{peer}/receive_block", json=block_data, timeout=3)
        except Exception as e:
            logger.error(f"[BROADCAST] {peer} へのブロードキャスト失敗: {e}")


@app.post("/receive_block")
def receive_block(block_data: dict):
    """他のノードから受信したブロックを検証し、チェーンに追加する"""
    global blockchain

    # ブロックの復元
    new_block = Block(
        block_data["index"],
        block_data["previous_hash"],
        block_data["timestamp"],
        block_data["data"],
        block_data["difficulty"],
    )
    new_block.nonce = block_data["nonce"]
    new_block.hash = block_data["hash"]

    # 検証
    last_block = blockchain[-1]

    # 既にこのインデックスのブロックがある場合はスキップ
    if new_block.index <= last_block.index:
        return {"status": "rejected", "reason": "already have this block or newer"}

    # インデックスが連続していない場合は同期が必要
    if new_block.index > last_block.index + 1:
        sync_chain()
        return {"status": "syncing", "reason": "need to sync chain first"}

    # 前のブロックとの関連を検証
    if new_block.previous_hash != last_block.hash:
        return {"status": "rejected", "reason": "invalid previous hash"}

    # ハッシュの検証
    if new_block.hash != new_block.calculate_hash() or not new_block.hash.startswith(
        "0" * difficulty
    ):
        return {"status": "rejected", "reason": "invalid hash"}

    # ブロックを追加
    blockchain.append(new_block)
    logger.info(f"[RECEIVED] 新しいブロックを受け入れました: {new_block.index}")
    return {"status": "accepted"}


# -------------------- ピア管理 --------------------
@app.post("/peers")
def add_peer(peer: dict):
    """
    受信した情報により相手ノードのURLを登録する。
    すでに登録済みの場合はスルーする。
    さらに、自分情報を返すことで双方向通信を確立する仕組みも含む。
    """
    url = peer.get("url")
    if url and add_peer_if_new(url):
        logger.info(f"[PEER] {url} を登録")
        # 相手に自分も登録してもらう
        try:
            requests.post(f"{url}/peers", json={"url": MY_NODE}, timeout=3)
            logger.info(f"[PEER] {url} に自ノード情報を返送")
        except Exception as e:
            logger.error(f"[ERROR] {url} への返送失敗: {e}")

    return {"peers": peers}


@app.get("/peers")
def get_peers():
    return {"peers": peers}


# -------------------- チェーン同期 --------------------
@app.post("/sync")
def sync_chain():
    global blockchain
    longest_chain = blockchain
    max_length = len(blockchain)

    for peer in peers:
        try:
            res = requests.get(f"{peer}/chain", timeout=5)
            peer_chain_data = res.json()

            # 受信したチェーンデータを変換
            peer_chain = []
            for b in peer_chain_data:
                block = Block(
                    b["index"],
                    b["previous_hash"],
                    b["timestamp"],
                    b["data"],
                    b["difficulty"],
                )
                block.nonce = b["nonce"]
                block.hash = b["hash"]
                peer_chain.append(block)

            # チェーンが有効で、かつ自分のチェーンより長い場合は置き換え
            if len(peer_chain) > max_length and is_chain_valid(peer_chain):
                longest_chain = peer_chain
                max_length = len(peer_chain)
                logger.info(
                    f"[SYNC] 長いチェーンが {peer} から取得されました: {max_length} ブロック"
                )
        except Exception as e:
            logger.error(f"[ERROR] {peer} との同期失敗: {e}")

    if len(longest_chain) > len(blockchain):
        blockchain = longest_chain
        return {"status": "replaced", "length": len(blockchain)}
    else:
        return {"status": "kept", "length": len(blockchain)}


@app.get("/status")
def get_status():
    """ノードのステータス情報を返す"""
    return {
        "node": MY_NODE,
        "chain_length": len(blockchain),
        "peers": len(peers),
        "difficulty": difficulty,
        "last_block": vars(blockchain[-1]) if blockchain else None,
    }


# -------------------- サーバ起動（単体実行の場合） --------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("node:app", host="0.0.0.0", port=PORT, reload=True)

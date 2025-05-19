# FastAPI Blockchain Node

このリポジトリは、FastAPIを用いて構築されたシンプルなProof-of-Work(PoW)方式のブロックチェーンノードの実装です。複数ノードが相互に通信しながらブロックチェーンを同期します。開発や教育目的での使用を想定しています。

## メイン機能

* ブロックの生成とマイニング
* チェーンの取得
* ピア同士の同期 (ブロードキャスト)
* IP自動検出とノード情報の保存
* プルーフオブワークチェーン検証

## 使用技術

* Python 3.x
* FastAPI
* Uvicorn
* requests
* netifaces
* hashlib / json / threading / logging

## 使い方

### 1. 環境構築

```bash
pip install -r requirements.txt
```

[Tailscale](https://tailscale.com/)を導入

### 2. 起動

```bash
python blockchain_node.py
```

起動時にIPを自動検出し、`node_config.json`に保存されます。

### 3. エンドポイント

| メソッド | パス       | 概要                                                                                 |
| ---- | -------- | ---------------------------------------------------------------------------------- |
| GET  | `/chain` | 現在のブロックチェーンをJSONで返信                                                                |
| POST | `/mine`  | 新しいブロックを作成し、マイニング                                                                  |
| GET  | `/peers` | 登録済みのピア情報を返信                                                                       |
| POST | `/peers` | 新しいピアを登録 ({ "url": "[http://xxx.xxx.xxx.xxx:8000](http://xxx.xxx.xxx.xxx:8000)" }) |

## 特殊解説

### ピア同期

* `PEERS_CANDIDATE` のIPリストを先に、ピアを検索し同期します
* 30秒ごとに背景で同期が起動
* `node_config.json` を用いてIP情報を保存

### マイニング

* POST `/mine`により、クライアントのIPを判別
* 特定IP(`100.75.238.65` / ご自身の環境に合わせてください。)は攻撃用データとして記録
* 新ブロックは他ノードにブロードキャスト


## 注意

* 本システムは教育用のデモブロックチェーンです
* 実際のセキュリティを考慮したブロックチェーンシステムの代用は推奨しません

## License

This project is released under the MIT License.

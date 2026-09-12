# Alias Unit Server (Alias Sender PoC)

SMPTE ST2110 / AMWA NMOS (IS-04 / IS-05) 環境において、あるゾーンに実在する
Real Senderを、別ゾーンのRDSに対して「別名のSender(Alias Sender)」として
代替登録し、Receiver/ブロードキャストコントローラーがReal Senderに一切
アクセスせずにSDP情報を取得・IGMP Joinできるようにする検証用(PoC)システムです。

詳細仕様は要件定義書([docs/Alias_Sender要件定義書.pdf](docs/Alias_Sender要件定義書.pdf))の①〜⑭章を正とします。
実装上の解釈・判断は [DECISIONS.md](DECISIONS.md) を参照してください。

## 前提条件

- Docker Engine / Docker Compose v2 (`docker compose` サブコマンド) がインストールされていること
- Linuxホスト、またはDocker Desktop for Windows/Mac(WSL2バックエンド)。
  **`network_mode: host` はLinuxホスト上で最も確実に動作します**。
  Docker Desktop for Windows/Macではhostネットワークモードの挙動がOSにより
  異なるため、本番検証は Ubuntu Server 24.04 上のDocker Engineを推奨します
  (要件定義書⑤a)。
- 同一ゾーンRDSおよび他ゾーンRDS(nmos-cpp等)へネットワーク到達可能であること

## 起動方法

```bash
docker compose up -d --build
```

これだけで、WebGUI + REST管理API + NMOS Node/Connection APIサーバーが
1つのコンテナ内で起動します。デフォルトでは `http://<ホストIP>:8000/` から
WebGUIにアクセスできます。

- SQLiteのDBファイルは `./data/alias_sender.db` にホスト側マウントされ、
  コンテナ再起動後も設定は保持されます(NFR-01)。
- ログは `./logs/app.log` に出力されます(NFR-03)。
- コンテナは `network_mode: host` で起動するため、AliasNodeごとに動的に
  割り当てられるNode API/Connection APIのポートも、Docker側の設定変更なしに
  そのままホストへ公開されます(NFR-07)。

### 主な環境変数 (`docker-compose.yml`で設定)

| 変数名 | デフォルト | 説明 |
| --- | --- | --- |
| `ALIAS_WEB_PORT` | `8000` | WebGUI/管理APIの待受ポート(初回起動時のみ有効。以後はWebGUIの「システム設定」画面から変更した値がDBに保存され優先される) |
| `ALIAS_NODE_API_PORT_START` | `10080` | AliasNode作成時の推奨開始ポート番号(GUI上の初期値目安) |
| `ALIAS_DB_PATH` | `/app/data/alias_sender.db` | SQLiteファイルパス |
| `ALIAS_LOG_DIR` | `/app/logs` | ログ出力先 |
| `ALIAS_HEARTBEAT_INTERVAL_SECONDS` | `5.0` | Registration APIハートビート間隔 |
| `ALIAS_QUERY_POLL_INTERVAL_SECONDS` | `30.0` | 同一ゾーンRDS Query APIのポーリング間隔(WebSocket補完用) |

## 基本的な使い方(要件定義書⑧の運用フローに対応)

1. 「RDS登録管理」画面で、同一ゾーンRDS(Query API接続先)を設定しON にする
2. 「Alias Nodeの作成管理」画面で、各ゾーン向けのAlias Nodeを作成する
   (label、Node API ON/OFF、ポート番号)
3. 「Alias Device/Connectorの作成管理」画面で、AliasDevice/AliasConnectorを
   作成し、X-Yクロスポイントで作成したAlias NodeとAlias Deviceを紐づける
4. 「Alias Senderの作成管理」画面で、取得済みのReal Senderを選択し、
   Connectorに紐づけてAlias Senderを作成する(V/A/ANCの3種類まで)
5. 「RDS登録管理」画面で、他ゾーンRDS(Registration API接続先)をAliasNode
   単位で追加する。以降は自動的に登録・5秒間隔のハートビート・SDP同期が
   継続する
6. 他ゾーンのReceiver/ブロードキャストコントローラーから、Alias Sender経由
   でSDPを取得し、IGMP Joinできることを確認する(③4, 最終ゴール)

## ローカル開発(Dockerを使わない場合)

### バックエンド

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

テスト実行:

```bash
cd backend
pytest tests -q
```

デモ用シードデータ投入(実RDSがなくてもWebGUIの見た目を確認できます):

```bash
cd backend
python scripts/seed_demo_data.py
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

Vite dev serverは `http://localhost:5173` で起動し、`/api` へのリクエストは
`http://localhost:8000` にプロキシされます(`vite.config.ts`)。

## ディレクトリ構成

```
backend/app/
  db/            SQLiteスキーマ(⑩の9テーブル)
  services/      同期エンジン・Registration/Query APIクライアント・
                 SDP解析・AliasSenderロジック等
  nmos/          AliasNode向けNode API(IS-04)/Connection API(IS-05)の
                 リソースビルダーとサブアプリ
  api/routers/   WebGUI向けREST管理API
frontend/src/
  views/         ⑨で定義された6つの管理画面
```

## 既知の制約(PoCとしてのスコープ、⑬参照)

- 認証・認可・HTTPS化は行いません(OOS-01, OOS-02)。すべてHTTP平文・無認証です。
- Alembic等のマイグレーションツールは使用せず、起動時に`create_all`でスキーマを
  保証します(DECISIONS.md参照)。
- Flowリソースは生成しません。Sender.flow_idにはSource IDを暫定的に流用します
  (⑪6, DECISIONS.md参照)。
- WebSocket通知は、GRAINのpre/post差分を個別適用せず、通知受信をトリガーに
  Query APIへの全件reconcileを行う簡易実装です。
- DBインポート後はバックグラウンドエンジンの完全な再同期のため、コンテナ再起動を
  推奨します(REQ-H08)。

## 受け入れ基準(⑭)に対する自己チェック

| 検証項目 | 状態 | 備考 |
| --- | --- | --- |
| AC-A01〜A05 同一ゾーンRDS連携の正常系・異常系 | 実装済み・単体テストで一部検証 | 実RDS(nmos-cpp)との結合試験は未実施。ロジック(オフライン検知/復旧/SDP同期)は`tests/test_alias_sender_logic.py`でカバー |
| AC-B01〜B04 AliasNode管理 | 実装済み | 排他制御はDBのユニーク制約+APIの409応答で実現 |
| AC-C01 X-Yクロスポイントによる多対多紐づけ | 実装済み・単体テストで検証 | `tests/test_node_scope.py` |
| AC-C02 AliasConnectorのV/A/ANC制約 | 実装済み・単体テストで検証 | `tests/test_alias_sender_logic.py` |
| AC-D01〜D04 AliasSender管理・SDP同期 | 実装済み・単体テストで検証 | label自動生成、SDP非改変同期、Source自動生成、media_type独立性を確認 |
| AC-E01〜E02 他ゾーンRDS登録・ハートビート | 実装済み | ユーザーの実RDS(nmos-cpp)での試験で判明したSender登録400エラー(flow_idの参照整合性、Flowスキーマの必須フィールド不足)を修正済み。生成するSource/Flow/Senderリソースは、実際のAMWA IS-04 v1.3 JSON schemaに対する検証テスト(`tests/test_nmos_schema_compliance.py`)でカバーしている |
| AC-F01〜F03 Node API/Connection API | 実装済み・手動結合確認済み | ローカルでAliasSender作成→動的ポートでのNode API `/self`, `/senders`, `/senders/{id}/transportfile`, Connection API `/active`, `/receivers`(空配列)の応答を確認済み |
| AC-F04 実機でのIGMP Join成功(最終ゴール) | **未検証** | 実機のNMOS RDS/Receiver/ブロードキャストコントローラーが必要なため、本開発環境では検証できません |
| AC-H01〜H03 WebGUI表示 | 実装済み・ビルド確認済み | `tsc --noEmit`, `vite build`, および統合起動での応答確認済み。実ブラウザでの目視確認は未実施 |
| AC-H03 DBエクスポート/インポート | 実装済み | `.db`ファイルのダウンロード/アップロードAPIを実装 |

**総括**: 本PoCの最終ゴール(AC-F04: 実機でのIGMP Join成功)および実RDSとの
結合試験は、開発環境に実機・実RDSが存在しないため未検証です。それ以外の
機能要件(REQ-A〜H)はコード実装および可能な範囲の自動テスト・手動結合確認
(ローカルでの同一プロセス内API呼び出し)によって動作を確認しています。
実機環境での最終検証を強く推奨します。

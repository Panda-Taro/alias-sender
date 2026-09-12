# 実装上の判断メモ (DECISIONS)

要件定義書(⑩〜⑭章)に明記のない、または解釈が必要だった実装詳細について、
判断内容と理由を記録する。詳細仕様は常に添付PDFが正。

## マイグレーション
- PoCのため Alembic は導入せず、SQLAlchemy の `Base.metadata.create_all()` を
  アプリ起動時に実行する方式とする。理由: PoCの検証コスト(⑬NFR-06/OOS-05相当の
  過剰投資回避)。将来の本番化ではAlembic移行を推奨。

## Node API / Connection API のポート分離
- 1台のプロセス内で AliasNode ごとに `node_api_port` を割り当て、
  `uvicorn.Server` を asyncio タスクとして動的に起動/停止する
  (`NodePortServerManager`)。各サーバーは同一のルート定義(FastAPIサブアプリ)を
  使うが、生成時に `node_id` をクロージャで束縛することでスコープを分離する。
- AliasNodeの作成/更新(port変更)/削除/有効化切替のたびに該当ポートの
  サーバーを再起動する。

## SDPパース
- `sdp_transform` 相当の独自軽量パーサを実装(行ベースのSDP a=/m=/c=行解析)。
  PyPI上の信頼できる保守されたSDPパーサが限定的なため、SDPの構造は単純な
  key=value風の行フォーマットであり、必要な範囲(media type判定用のm=行)のみを
  正規表現で解析する自作の薄いユーティリティとした。SDP本体(生テキスト)は
  一切改変せず、判定結果のみを別カラムに保存する(④⑤の大前提を厳守)。

## WebSocket購読の実装
- `websockets` ライブラリを使用し、IS-04 Query API `/subscriptions` に
  POSTしてWebSocket URLを取得後、常時接続してGRAINメッセージを受信する。
  切断時は指数バックオフで再接続する。

## 認証/HTTPS
- ⑬OOS-01/OOS-02により実装しない。すべてHTTP平文・無認証。

## DBエクスポート/インポート
- REQ-H08通り、SQLiteファイル(.db)そのものをダウンロード/アップロードする
  方式とし、アップロード時はアプリを再起動せずにDBコネクションを再オープンする
  簡易実装とする(PoCのため、アップロード後はコンテナ再起動を推奨する旨README
  に記載)。

## フロントエンド
- React + Vite + Tailwind (ダークテーマ)。状態管理はReact Query(TanStack Query)
  でポーリングベースの自動更新を行う(WebGUI自体のリアルタイムpushは要件外)。

## WebSocket通知の適用方式
- GRAINメッセージの中身(pre/post差分)を細かく適用するのではなく、WebSocketで
  何らかの更新通知を受信したことをトリガーとして、Query APIへの全件reconcile
  (REQ-A01相当の再取得)を即時実行する方式とした。これにより、GRAINのpre/post
  パース漏れによる状態不整合を避け、必ずQuery APIの応答を正として同期する。
  reconcileは差分検出(新規/更新/消失)を内部で行うため、結果としてREQ-A04/A05/A06
  の要件は満たされる。

## テスト
- 要求された「最低限のユニットテスト」として、SDP同期ロジック、オフライン検知
  ロジック、Nodeスコープフィルタリングの3点に絞る(pytest)。

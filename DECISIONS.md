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

## OSのIPアドレス表示 (運用フィードバック対応)
- `socket.gethostname()`経由の解決はコンテナの`/etc/hosts`次第でOS上の実際の
  インターフェースIPと一致しないことがある(`--network host`環境で特に顕著)。
  そのため`ip -o -4 addr show`(なければ`ifconfig`、さらにフォールバックで
  ソケットAPI)の出力を実際に解析して表示するように変更した
  (`app/services/host_info.py`)。Dockerイメージに`iproute2`を追加インストール
  している。

## WebGUI待受ポートの動的変更 (運用フィードバック対応)
- WebGUI/管理APIのポートを、コンテナ再起動なしにGUIから変更できるようにする
  ため、`uvicorn app.main:app`をCLIから直接起動する構成をやめ、
  `app/run.py`を自前のエントリーポイントとし、`WebServerManager`
  (`app/services/web_server_manager.py`)が`uvicorn.Server`を
  asyncioタスクとして管理する。ポート番号は`SystemSettings`テーブル
  (新規、シングルトン)に永続化し、GUIでの変更は
  `PUT /api/system/web-port`→バックグラウンドで`restart()`という流れになる。
  リクエスト自体は旧ポートのサーバーが処理しているため、レスポンスを返した
  後に非同期で切替えを行う(同期的に行うとサーバー自身の停止待ちでデッドロック
  するため)。
- `docker compose`から見た待受ポートは実質「GUI上の設定が正」になるため、
  `docker-compose.yml`のポートマッピングという概念自体が無い
  (`network_mode: host`によりホストの全ポートが直接コンテナに見える)ことと
  整合する。

## Registration APIの耐障害性 (運用フィードバック対応: Alias Nodeの点滅・
   ダッシュボードの赤色固定・Senderが認識されない)
- 従来は1つのZoneRdsConfigに対する処理(Node/Device/Source/Flow/Sender登録+
  ハートビート)を1つのtry/exceptで囲っていたため、Sender登録が何らかの理由
  (後述のFlow参照不整合など)で失敗すると、その回のハートビート送信自体が
  スキップされていた。IS-04のRDS実装はハートビートが数サイクル途絶すると
  Nodeを期限切れとして削除するため、これが「他ゾーンRDSでAlias Nodeが表示
  されたり消えたりする」不具合の直接原因だった。
- 対応として、Node登録失敗時のみ処理を中断し、Device/Source/Flow/Sender登録は
  1件ずつ例外を捕捉して継続、ハートビートは(Node登録が成功していれば)
  常に最後に試行する構成に変更した(`app/services/registration_engine.py`)。
  `ZoneRdsStatus`に`senders_ok`/`senders_total`を追加し、ダッシュボードで
  「何件中何件が登録できているか」と直近のエラー文字列を表示できるようにした。

## Flowリソースの追加 (運用フィードバック対応: 他ゾーンRDSでSenderが認識され
   ない)
- 従来はSenderリソースの`flow_id`にSource ID(Sourceリソースのid)を代用して
  いたが、IS-04のRDS実装(nmos-cpp等)は参照整合性を検証するため、
  「flow_idが実際に登録されたFlowリソースを指していない」ことがSender登録の
  400エラーの原因になり得る。これは前述のハートビート問題とあわせて、
  「Node/Deviceは認識されるがSenderは認識されない」という報告と整合する。
- 対応として、`source_id`から決定的に導出した`flow_id`
  (`resources.derive_flow_id`, `uuid5`)を持つ最小限のFlowリソースを
  実際にRegistration APIへ登録し、Node APIにも`/flows`, `/flows/{id}`を追加
  した。技術パラメータ(フレームサイズ、ビット深度、サンプルレート等)は
  SDPのfmtp/rtpmapから読み取れる範囲で反映し、読み取れない項目は一般的な
  放送用途の既定値(1920x1080 progressive BT709、24bit等)にフォールバックする
  近似実装であり、完全なSDP fmtp解析は行っていない。

### 実際の400エラーで判明した具体的なスキーマ不備(確定原因)
AMWA公式のIS-04 v1.3 JSON schema(`AMWA-TV/nmos-discovery-registration`
リポジトリ、`tests/schemas/`に検証用として同梱)を取得し、生成JSONを実際に
検証したところ、以下3点の不備が判明した。これがユーザー報告の
「video/audio/ancillaryの全Senderが400 Bad Requestで登録失敗」の確定原因
である:
1. `flow_core.json`は`device_id`を必須プロパティとして要求する(v1.1以降)。
   `build_flow_resource`にこのフィールドが欠落していた → 全media_typeで
   Flow登録が400になり、結果としてSenderも登録されなかった。
2. `flow_video_raw.json`は`components`(Y/Cb/Cr等のプレーンごとの
   width/height/bit_depthの配列、最低1要素)を必須とする。videoのFlowにこの
   フィールドが欠落していた。既定値として4:2:2 10bitを仮定して近似生成する
   ことにした(正確なサブサンプリング/ビット深度はSDPのfmtpから完全には
   判定していない)。
3. `source_audio.json`のchannels[].symbolに`"M"`という値を設定していたが、
   これはVSF TR-03 Appendix Aで定義された固定enum
   (`L,R,C,LFE,Ls,Rs,...,M1,M2,...`)のいずれにも一致せず無効な値だった。
   モノラルを表す`"M1"`に修正した。

再発防止のため、`tests/test_nmos_schema_compliance.py`で生成した
Source/Flow/Senderリソースを実際のAMWA IS-04 v1.3 schemaに対して
`jsonschema`で検証するテストを追加した。手作業でのフィールド確認だけでは
このクラスの不備(必須フィールド欠落、enum値の誤り)を見逃していたため。

## NMOSリソースversionフィールドの安定化
- 従来は登録/自己記述の都度`version`を現在時刻から生成していたため、内容が
  変化していなくても5秒毎(ハートビート間隔)に`version`が変わり、受信側に
  不要なMODIFIED通知を発生させ続けていた。これも表示のちらつきの一因になり
  得るため、リソースの内容をハッシュ化し、前回と同一であれば同じversion
  文字列を再利用するキャッシュ(`resources._stable_version`)を追加した。

## Node API/Connection APIサブアプリへのCORS許可 (運用フィードバック対応:
   NMOS ExplorerでSenderを開くと「Cannot connect」)
- RDS経由でNode/Device/Senderの一覧表示は成功するが、NMOS Explorer(ブラウザ/
  Electronベースのツール)でSenderをクリックして詳細を見ようとすると
  「Internal error: Cannot connect」になる、という報告があった。これは
  ツールがRDSのキャッシュではなく、Sender/Nodeが自己申告するhost:port
  (本システムのNode API)へ直接(P2P)アクセスして詳細情報や接続状態を取得する
  実装になっているためで、ブラウザのfetch/XHRがCORSヘッダーの無い
  レスポンスをブロックすると、JS側には(CORSエラーではなく)汎用的な
  「接続できない」ように見えるエラーとして現れる。
- メインアプリ(`app/main.py`)には元々`CORSMiddleware`を設定していたが、
  AliasNodeごとに動的生成される`create_node_app()`のサブアプリには設定して
  いなかった。これが原因のため、Node API/Connection APIサブアプリにも同様の
  ワイルドカードCORS許可を追加した。

## Alias Connector更新APIのリクエスト形式変更
- `PUT /api/alias-connectors/{id}`は当初`connector_label`をクエリパラメータ
  として受け取っていたが、他の更新APIと一貫させ、WebGUI全体に「編集」操作を
  設けるにあたりフロントエンドの実装を統一するため、JSONボディ
  (`{"connector_label": "..."}`)を受け取る形式に変更した。

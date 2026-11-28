# タイヤ価格監視システム 全体仕様

155/65R14 タイヤの価格監視システムの全部の機能・ロジック・仕組みを、他のエージェントが再現・保守できる粒度で記述する。
要約版は [README.md](README.md)。公開ページ: https://jerrybmg9728.github.io/tire-price-monitor/
（本書は 2026-11-28 時点の実装に基づく）

## 1. 全体構成

| コンポーネント | 実体 | 役割 |
|---|---|---|
| 本体スペース「タイヤ監視システム」 | Muse Space（fullstack）、slug `taiyajian-shi-sisutemu` | 状態保持・画面表示・アクション `getState` / `refreshPrices` の提供 |
| 価格チェックジョブ | cron `taiya-price-watch-daily`（1時間間隔、毎時 :31 JST 起動、kind=space_action） | 本体の `refreshPrices` を毎時起動する |
| 共有版スペース | Muse Space（静的・client-only）、slug `taiyajia-ge-jian-shi-gong-you-ban` | 共有ページの元データ。サーバーアクションは持たない |
| 共有版更新ジョブ | cron `taiya-share-refresh-hourly`（1時間間隔、毎時 :50 JST 起動、kind=agent） | 本体の最新データを共有版へ反映する（GitHub 公開は行わない） |
| GitHub 公開 | リポジトリ `jerrybmg9728/tire-price-monitor`（GitHub Pages、branch `main`） | 共有版 HTML を `index.html` として公開。更新はメインエージェントが実行 |
| GitHub 接続 | カスタムコネクタ `custom.github`（fine-grained PAT、対象リポジトリのみ Contents read/write、値は Secure Vault 保管） | API 経由のファイル更新。ヘルパー: `~/workspace/custom-connectors/custom.github/bin/github_api.py` |
| 運用ゴール | goal `155-65r14-tire-price-monitoring`（ID: goal_ed919a5cc7ca） | 両 cron の owner。実行ログや中間ファイルは `~/workspace/goals/155-65r14-tire-price-monitoring/hidden_files/` に置く |

## 2. 監視対象（watch_targets、3件）

| id | 名称 | season | 検索クエリ |
|---|---|---|---|
| 1 | ブリザック VRX3（冬用） | winter | ブリヂストン ブリザック VRX3 155/65R14 75Q スタッドレスタイヤ 価格 |
| 2 | 夏タイヤ（サマー） | summer | 155/65R14 夏タイヤ サマータイヤ 価格 軽自動車 |
| 3 | wz-1 | winter | wz1 |

全ターゲット共通でサイズは 155/65R14。

## 3. データモデル

本体スペースが保持する状態（`getState` の返却構造）:

- `latestRun`: 直近のチェック実行 `{ requestedAt, finishedAt, status (running/succeeded/failed), message }`
- `targets[]`: ターゲットごとの状態
  - 基本情報: `id, name, brandModel, query, season, size`
  - `latest`: 最新スナップショット（下記）
  - `offers[]`: 最新チェックで確認した出品（下記）
  - `history[]`: 過去のスナップショット列（時系列）
  - `previousLowestUnitPrice`: 前回チェックの最安単価（前回比の算出用）

スナップショット（`latest` / `history[]` の各要素）:

| フィールド | 意味 |
|---|---|
| `basis` | 集計基準。`main4` = 主要4市場のみ（2026-11-26 以降）、`legacy` = 参考価格込みの旧基準 |
| `checkedAt` / `date` | チェック完了時刻（ISO 8601、UTC） |
| `lowestUnitPrice` | 主要4市場の最安単価（1本あたり）。出品なしなら null |
| `lowestSetPrice` | 4本あたりの最安価格（最安出品のセット価格、単品の場合は単価×4換算） |
| `lowestStore` / `lowestMarketplace` / `lowestUrl` | 最安出品の店舗・市場・商品ページ URL（根拠リンク） |
| `medianUnitPrice` | 主要4市場の単価の中央値（相場） |
| `offerCount` | 確認した全出品数（参考価格込み） |
| `mainOfferCount` | 主要4市場の出品数 |
| `referenceOfferCount` | 参考価格の出品数 |
| `status` | `ok` / `no_results`（主要4市場の出品が0件） |
| `note` | 除外した出品とその理由、市場の欠けなどの注記（日本語の自由文） |

出品（`offers[]` の各要素）:

| フィールド | 意味 |
|---|---|
| `id` | 出品レコード ID |
| `isMain` | 主要4市場の出品なら true、参考価格なら false |
| `marketplace` | 楽天市場 / Yahoo!ショッピング / ヤフオク! / Amazon / その他 |
| `store` | 店舗名 |
| `title` | 商品タイトル |
| `price` | 表示価格（セット価格ならセット総額） |
| `quantity` | 本数（1 または 4） |
| `unitPrice` | 単価 = price ÷ quantity |
| `shipping` | 送料（無料=0、不明=null）。単価比較には含めない |
| `url` | 商品ページ URL |

内部テーブル（2026-11-28 の診断時点）: `watch_targets` 3件、`check_runs` 111件、`snapshots` 280件、現在の `offers` 22件。

## 4. 価格チェックのロジック（refreshPrices）

1. 起動ガード: 既に実行中の run がある場合、新規開始せず `{ started: false }` を返す（手動・自動とも二重起動しない）。開始できれば `{ started: true, runId }` を返し、`check_runs` に run レコードを作る。
2. バックグラウンドの調査タスク（space_task エージェント）がターゲットごとに検索クエリで各市場を調査し、出品を収集する。
3. 出品の正規化: 商品ページでタイトル・店舗・本数・送料を確認し、`unitPrice = price ÷ quantity` で単価化する。
4. 市場の分類: 楽天市場、Yahoo!ショッピング、ヤフオク!、Amazon を主要4市場（`isMain: true`）とする。モノタロウ、ヨドバシ.com、その他店舗は参考価格（`isMain: false`）。
5. 除外ルール（除外理由は `note` に記録する）:
   - 終了済みのオークション、即決価格が曖昧なヤフオク!出品
   - 価格情報が古い、または当日商品ページで確認できない出品（例: ページが 403 で価格が過去時点のもの）
   - サイトエラー（503 等）で当日確認できない市場はそのチェックでは欠けとして扱う
6. 集計（主要4市場のみ）:
   - 最安単価 = 主要出品の `unitPrice` の最小値。その出品の店舗・市場・URL を根拠として記録
   - 中央値 = 主要出品の `unitPrice` の中央値
   - 主要出品が0件なら `status: no_results` とし、最安・中央値は null（参考価格のみ記録）
7. 完了処理: スナップショットを `history` に追加し、`offers` を最新の出品に入れ替え、`previousLowestUnitPrice` を更新、run を完了にする。

### 集計基準の変更履歴

- 2026-11-26: 最安値・中央値の算出を主要4市場のみに変更（ユーザーの決定。「実際にタイヤが売れる場所」だから）。参考価格は表示のみに残す。
- グラフは `basis: main4` の履歴ポイントだけを描画する。旧基準（legacy）の履歴行には「旧基準（参考価格を含む）」の表示を付ける。

## 5. 実行ライフサイクルと障害対策

- チェックは通常、起動（毎時 :31）から数分〜10分程度で完了し、結果が本体に反映される。
- **45分タイムアウト回収（2026-11-28 追加）**: 開始から45分以内に調査タスクから完了報告がない run は、自動で `failed`（タイムアウト）として確定させる。`latestRun` も failed を返す。これにより、固まった run が後続のチェックや画面表示を塞がない。
- 障害事例（2026-11-27〜28）: 19:40 完了のチェックを最後に、調査タスクが完了報告を返さない事象が17件連続し、run が `running` のまま固着。画面は「チェック中…」を表示し続け、手動チェックも開始できなかった。cron 自体は毎時正常に `refreshPrices` を呼んでいた（ディスパッチ成功 ≠ チェック完了）。調査タスクが報告を返さなかった根本原因はアーティファクト側に記録が残らず未特定。
- 監視の要点: 正常性は cron の実行成否ではなく「各ターゲットの `latest.checkedAt` が進んでいるか」で判断する。

## 6. 共有ページの生成と公開フロー

1. 毎時 :50 の共有版更新ジョブ（agent）が本体の `getState` を取得する。
2. 共有版の表示データ時点より新しいチェック結果がなければ、何もせず終了する（報告もしない）。
3. 新しいデータがあれば、共有版スペースを編集して最新データに更新する。構成は本体と同じ:
   - 最安値ボード（単価・4本セット価格・店舗・前回比）
   - 価格推移グラフ（最安単価と中央値の2系列、横軸はチェック時刻、刻みは6時間: 00時・06時・12時・18時）
   - 商品ページへのリンク付き出品一覧
   - 相場メモ
   - チェック履歴
4. ジョブ内では GitHub 公開を行わない。ハンドオフを受けたメインエージェントが次を行う:
   - `artifact.export`（slug `taiyajia-ge-jian-shi-gong-you-ban`）で HTML 化 → `~/workspace/your_files/taiyajia-ge-jian-shi-gong-you-ban/taiyajia-ge-jian-shi-gong-you-ban.html`
   - `python3 ~/workspace/custom-connectors/custom.github/bin/github_api.py put-file jerrybmg9728 tire-price-monitor index.html <exportファイル>` で `index.html` を更新
5. 成功時はユーザーへ報告しない。失敗した場合のみ、失敗した手順と理由を簡潔に報告する。
6. 共有版は client-only のため `getState` を持たない。表示時点の照合は watermark ファイル `~/workspace/goals/155-65r14-tire-price-monitoring/hidden_files/share-refresh-state.md` と、実行ごとの記録（`latest-state-*.json`、`share-edit-request-*.txt`、同フォルダ）で行う。
7. 旧来の muse.ai 共有リンクは 2026-11-26 の GitHub Pages 移行後は更新していない。

## 7. スケジュール一覧

| ジョブ ID | 間隔 | 起動 | 種別 | 実行内容 |
|---|---|---|---|---|
| `taiya-price-watch-daily` | 1時間 | 毎時 :31 JST | space_action | 本体 `refreshPrices`（価格チェック） |
| `taiya-share-refresh-hourly` | 1時間 | 毎時 :50 JST | agent | 共有版の編集まで（公開はメインエージェント） |

## 8. トークン使用量（実測）

2026-11-28 にエージェント実行記録（`agent.agent_message_token_usage`）を集計した実測値:

- 価格チェック1回 = 調査タスク（space_task エージェント）1体分
  - 直近36回分: 平均 入力 約1,530,000 トークン / 出力 約9,900 トークン（合計 約154万トークン/回）
  - 通常回の範囲: 入力 約47万〜約250万トークン（調査量により変動。最大約669万の外れ値あり）
  - 毎時実行のため、チェックだけで 1日あたり約3,700万トークン規模
- 共有版の更新がある回は、別途エージェント（ジョブ本体＋ページ編集）が数十万〜約150万トークン程度を追加で使用する（実測の目安）

## 9. 運用上の注意

- 価格の上下は、値付けの変更よりも安い出品の出現・終了によるものが大半。
- VRX3 の最安フロアは 1本 ¥7,000（4本 ¥28,000、モーターズボックス楽天市場店）が繰り返し観測されている。
- WZ-1 は 2025年9月発売の新モデルのため 155/65R14 の流通が少なく、主要4市場で出品なし（no_results）になる回が多い。
- 購入を判断する前に、商品ページで在庫・送料・製造年を必ず確認すること（出品によっては個人宅配送不可などの制限がある）。

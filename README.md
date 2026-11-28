# タイヤ価格監視（155/65R14）

楽天市場・Yahoo!ショッピング・ヤフオク!・Amazon の新品出品を1時間ごとに自動で集計し、
最安値と相場の推移を公開するページです。AIは使わず、各市場の公式APIと決まったルールだけで集計します。

公開ページ: https://jerrybmg9728.github.io/tire-price-monitor/
詳しい仕様: [SYSTEM.md](SYSTEM.md)

## 監視対象（`config.yaml` で変更）

| id | 名称 | 条件 |
|---|---|---|
| vrx3 | ブリザック VRX3 | タイトルに VRX3 |
| summer | 夏タイヤ | スタッドレス・冬用などを含まないもの |
| wz1 | ブリザック WZ-1 | タイトルに WZ-1 |

## 見方

- **最安値**：条件に合う出品のうち、1本あたりで一番安いもの
- **上位3件の平均**：安い順に3件の平均。1件の出品が出たり消えたりしても跳ねにくい目安
- **中央値**：集まった出品全体の真ん中の価格（相場）
- 送料は単価に含めず、送料無料かどうかを表示

## 初期設定（キーの登録）

GitHub のリポジトリ → Settings → Secrets and variables → Actions に登録する。

| 名前 | 取得先 | 用途 |
|---|---|---|
| `YAHOO_APP_ID` | Yahoo!デベロッパーネットワークでアプリ登録 → Client ID | Yahoo!ショッピング |
| `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` | 楽天ウェブサービスでアプリ登録（WebサイトURLに公開ページのURLを登録） | 楽天市場 |
| （Variables）`RAKUTEN_ENDPOINT` | 楽天の最新版エンドポイントが変わったときだけ | 楽天市場 |

キーが無い市場は「未設定」と表示され、残りの市場だけで集計を続けます。ヤフオク!はキー不要です。

## 手元で動かす

```bash
pip install -r requirements.txt
python -m monitor.run --dry-run   # 取得と集計だけ（ファイルは書かない）
python -m monitor.run             # data/ と index.html を更新
python -m pytest -q tests         # テスト
```

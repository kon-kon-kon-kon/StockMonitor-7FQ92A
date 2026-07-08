# Stock Report

Yahoo!ファイナンスの売買代金ランキング上位150件を取得し、指定した下落率以下の銘柄だけをGitHub Pagesで表示します。

## GitHub Pages設定

- Source: Deploy from a branch
- Branch: main
- Folder: /docs

## 抽出条件

`.github/workflows/update.yml` の `DROP_THRESHOLD` で変更します。

- テスト: `-3.0`
- 通常運用: `-6.0`

## 保存方式

`docs/data.json` は毎回最新結果で上書きされます。過去の取得結果は画面に残りません。

# ZendeskSummarizer

**[ZendeskScrapper](../ZendeskScrapper) と組み合わせて使うツールです。**

ZendeskScrapper がダウンロードしたチケット HTML を Gemini API で解析し、各チケットフォルダに `summary.md` を生成します。生成された `summary.md` は ZendeskScrapper の Webアプリ（チケット詳細画面）で自動的に表示されます。

```
【ワークフロー】

ZendeskScrapper          ZendeskSummarizer        ZendeskScrapper
  scraper.py      →    summarize_zendesk.py   →     webapp.py
チケットHTMLを              summary.md を            詳細画面に
ダウンロード                  生成                  サマリーを表示
```

---

## 機能

- チケットフォルダ内の HTML ファイルを再帰的に処理
- BeautifulSoup で本文を抽出し、ノイズ（script/style など）を除去
- Gemini API に送信して技術要約を生成
- 各チケットフォルダに `summary.md` を出力
- Rate Limit 対策のスロットリング（15秒間隔）とエクスポネンシャルバックオフ

---

## 必要条件

- Python 3.8 以上
- Google Gemini API キー（[Google AI Studio](https://aistudio.google.com/) で取得）

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install beautifulsoup4 python-dotenv google-genai
```

### 2. `.env` ファイルの作成

プロジェクトルートに `.env` を作成し、以下を記述します。

```env
GEMINI_API_KEY=your_api_key_here
TARGET_DIR=C:/path/to/ZendeskScrapper/data/tickets
GEMINI_MODEL=gemini-2.5-flash
```

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | Gemini API キー（[Google AI Studio](https://aistudio.google.com/) で取得） |
| `TARGET_DIR` | 必須 | ZendeskScrapper の `data/tickets` フォルダへのパス |
| `GEMINI_MODEL` | 任意 | 使用モデル（デフォルト: `gemini-1.5-flash`） |

> **注意:** `.env` ファイルは Git にコミットしないでください。`.gitignore` に追加することを推奨します。

---

## 使い方

ZendeskScrapper で `scraper.py` を実行してチケットをダウンロードした後に実行してください。

```bash
python summarize_zendesk.py
```

### 期待するディレクトリ構造

```
TARGET_DIR/
├── ticket_001/
│   ├── conversation.html
│   └── attachment.html
├── ticket_002/
│   └── main.html
└── ...
```

### 出力

各チケットフォルダに `summary.md` が生成されます。

```
TARGET_DIR/
├── ticket_001/
│   ├── conversation.html
│   └── summary.md   ← 自動生成
└── ticket_002/
    ├── main.html
    └── summary.md   ← 自動生成
```

すでに `summary.md` が存在するフォルダはスキップされます（再処理なし）。

---

## 出力フォーマット

生成される `summary.md` の構成：

```markdown
# 案件要約

## 1. 議論していた内容
技術的課題の具体的な内容

## 2. 結論
解決策・回避策・現在のステータス

## 3. 要約
300文字程度のエンジニア向けサマリー

## 4. 最も参照すべき根拠ファイル
- ファイル名: xxx.html
- 理由: 重要な理由
```

---

## Rate Limit について

Gemini API の無料枠に配慮し、以下の制御を行っています。

- リクエスト間隔: 15 秒（1分あたり最大 4 リクエスト）
- 429 エラー時: 30秒から始まるエクスポネンシャルバックオフ（最大 5 回リトライ）

大量のチケットを処理する場合は時間がかかります。有料プランを使用する場合は `REQUEST_INTERVAL` の値を短縮できます。

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `ValueError: GEMINI_API_KEY または TARGET_DIR が設定されていません` | `.env` が存在しない、または変数が未設定 | `.env` ファイルを確認 |
| `[Warning] ファイル読み込み失敗` | HTML ファイルのエンコードが UTF-8 以外 | ファイルを UTF-8 で保存し直す |
| `!! Rate Limit発生` | API クォータ超過 | しばらく待つか、有料プランに移行 |
| 文字化け（Windows） | コンソールエンコード | スクリプトは自動対処済み。`chcp 65001` でも解消可 |

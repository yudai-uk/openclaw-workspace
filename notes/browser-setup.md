# Headless Browser Setup

## 現状
- ✅ Headless Chromeの設定完了
- ✅ CDPプロキシが動作中 (localhost:18800)
- ❌ Browserツールからアクセスすると拡張機能リレーのエラー

## 設定済み
```json
{
  "browser": {
    "headless": true
  },
  "commands": {
    "restart": true
  }
}
```

## 解決策
**Brave Search API keyを設定するのが一番確実**

### 手順
1. 以下のURLから無料のAPI keyを取得:
   https://brave.com/search/api/

2. ユーザーに教えてもらったら、以下のコマンドで設定:
   ```
   openclaw configure --section web
   ```
   API keyの入力を求められるので、取得したkeyを貼り付ける

3. 設定後、`web_search` と `web_fetch` が完全自動で使用可能になる

### 利点
- PCの前じゃなくても検索できる
- ウェブページを取得できる
- 拡張機能の手動アタッチが不要

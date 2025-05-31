# PhaseNavigator v1.2

固相のみの温度依存相図ジェネレーター。  
- **API キーはブラウザで一度入力 → AES-GCM 暗号化して localStorage に保存 → 以降自動送信**  
- **サーバー側はキーを保存せず SHA-256 ハッシュのみログ**  
- **簡易レートリミット** (10 req/30 s per key/IP) 実装  
- **ロゴ (static/logo.svg)** を全ページ上部に表示  
- 生成データは CC-BY-4.0 表記付き

## 起動
```bash
docker build -t phasenavigator .
docker run -p 8000:8000 phasenavigator

# My Line Robot (PDF Asker)

LINE Bot + LangChain + Gemini 的 PDF 問答機器人。

目前功能：
- 接收 LINE 文字訊息並依 PDF 內容回答
- 接收 LINE 上傳的 PDF 檔案（`.pdf`）
- 自動切分文件並建立/更新 Chroma 向量索引
- 遇到 Gemini 配額超限（429）時，回覆可讀提示

## 專案結構

```text
My_Line_Robot/
├─ pdfAsker.py
├─ README.md
├─ .env
├─ .gitignore
└─ data/
	 └─ uploads/
```

## 需求環境

- Python 3.10+
- LINE Messaging API Channel
- Google AI Studio API Key
- ngrok（本機 webhook 測試）

## 安裝套件

在專案根目錄執行：

```bash
pip install flask line-bot-sdk python-dotenv \
	langchain langchain-community langchain-text-splitters \
	langchain-google-genai langchain-huggingface chromadb
```

## 環境變數 `.env`

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_LINE_Channel_Secret
GOOGLE_API_KEY=你的_Google_API_Key
```

注意：
- `.env` 不要上傳到公開 repo
- 變數值不要加引號

## 啟動方式

```bash
python pdfAsker.py
```

預設啟動：`http://127.0.0.1:5000`

## ngrok 與 Webhook

1. 啟動 tunnel

```bash
ngrok http 5000
```

2. 到 LINE Developers 設定 Webhook URL 為：

```text
https://你的-ngrok-網址/callback
```

3. 開啟 `Use webhook` 並按 `Verify`

## 使用方式

1. 先在 LINE 上傳 PDF（副檔名需為 `.pdf`）
2. 再發送問題文字
3. Bot 會從已載入文件中檢索並回答

補充：
- 啟動時若存在 `data/GA04-GA-basic-1.pdf`，會先載入
- 後續上傳的 PDF 會存到 `data/uploads/`

## 常見問題

### 1) 出現 429 / RESOURCE_EXHAUSTED

代表 Gemini 配額達上限，請等待錯誤中的 `retry in xx s` 秒數後再試，或升級方案。

### 2) Bot 說「還沒有上傳 PDF」

代表向量庫沒有可用文件。請先上傳 PDF，或確認預設檔案路徑存在。

### 3) Webhook Verify 失敗

- 確認 `pdfAsker.py` 正在執行
- 確認 ngrok 指到 `5000`
- 確認 URL 最後是 `/callback`
- 確認 LINE token/secret 正確

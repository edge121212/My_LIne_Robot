# My Line Robot (PDF Asker)

這是一個 LINE Bot + Gemini 的 PDF 問答機器人。

你可以：
- 在 LINE 上傳 PDF 檔案（僅支援 .pdf）
- 直接提問，機器人會綜合 data 內所有 PDF 回答
- 用指令清除上傳來源

---

## 1. 專案結構

```text
My_Line_Robot/
├─ pdfAsker.py
├─ .env
└─ data/
	└─ uploads/
```

---

## 2. 需求環境

- Python 3.10+
- ngrok（用於把本機 webhook 暴露給 LINE）
- LINE Messaging API Channel
- Google AI Studio API Key（Gemini）

---

## 3. 安裝套件

在專案根目錄執行：

```bash
pip install flask line-bot-sdk google-generativeai python-dotenv
```

---

## 4. .env 設定（含 ngrok env）

在專案根目錄建立或編輯 .env：

```env
# LINE
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_LINE_Channel_Secret

# Gemini
GOOGLE_API_KEY=你的_Google_API_Key

# ngrok (可選，建議加上)
NGROK_AUTHTOKEN=你的_ngrok_authtoken
```

注意：
- .env 內請不要有多餘空白或引號。
- 不要把 .env 上傳到公開版本庫。

---

## 5. 啟動 Bot

```bash
python pdfAsker.py
```

預設會啟動在：http://127.0.0.1:5000

---

## 6. 設定 ngrok

### 6.1 第一次使用：設定 ngrok authtoken

方式 A（直接設定）：

```bash
ngrok config add-authtoken 你的_ngrok_authtoken
```

方式 B（使用環境變數，Windows PowerShell）：

```powershell
$env:NGROK_AUTHTOKEN="你的_ngrok_authtoken"
ngrok config add-authtoken $env:NGROK_AUTHTOKEN
```

### 6.2 建立對外 tunnel

```bash
ngrok http 5000
```

你會拿到一個公開網址，例如：

```text
https://xxxx-xxxx-xxxx.ngrok-free.app
```

---

## 7. LINE Webhook 設定

到 LINE Developers Console：

1. 打開你的 Messaging API Channel
2. Webhook URL 填入：

```text
https://你的_ngrok_網址/callback
```

3. 啟用 Use webhook
4. 按 Verify 測試是否成功

---

## 8. 使用方式

Bot 主要功能：

- 上傳 PDF：傳送 .pdf 檔案即可加入資料來源
- 問問題：直接輸入文字問題
- 查看說明：輸入 使用說明
- 清空上傳檔案：輸入 清除檔案

程式會讀取：
- data/ 下所有 .pdf
- data/uploads/ 下使用者上傳的 .pdf

---

## 9. 常見問題

### Q1: Verify Webhook 失敗

- 確認程式有在執行（port 5000）
- 確認 ngrok 連的是 5000
- 確認 Webhook URL 最後有 /callback
- 確認 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN 正確

### Q2: Bot 回覆找不到 PDF

- 確認 data 或 data/uploads 內有 .pdf
- 檔名副檔名必須是 .pdf

### Q3: Gemini 呼叫失敗

- 確認 GOOGLE_API_KEY 正確
- 確認 API key 有啟用可用模型

---

## 10. 開發備註

- 主要入口檔案：pdfAsker.py
- Flask endpoint：POST /callback
- 本機執行埠：5000

如果你要部署到雲端（Render / Railway / Azure），只要把相同環境變數帶上即可，不一定要使用 ngrok。

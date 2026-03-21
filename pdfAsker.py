import os
import google.generativeai as genai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FileMessage, FollowEvent
from dotenv import load_dotenv

# 1. 載入環境變數
load_dotenv()
app = Flask(__name__)

# 2. LINE 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 3. 配置 Gemini (強制使用 REST 協議避開舊版 bug)
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'), transport='rest')

# PDF 知識庫資料夾：會自動讀取裡面全部 .pdf
pdf_dir = "data"
upload_dir = os.path.join(pdf_dir, "uploads")

GREETING_MESSAGE = (
    "歡迎使用 Edge PDF 助理！\n\n"
    "你可以這樣使用：\n"
    "1. 直接上傳 PDF 檔案\n"
    "2. 傳文字問題給我，我會根據目前資料來源回答\n"
    "3. 若要清空剛上傳的檔案，請輸入：清除檔案\n"
    "4. 想再看一次說明，請輸入：使用說明\n\n"
    "提醒：目前只支援 .pdf 檔案。"
)


def _get_pdf_paths() -> list[str]:
    if not os.path.isdir(pdf_dir):
        return []

    paths = []
    for root, _, files in os.walk(pdf_dir):
        for name in sorted(files):
            if name.lower().endswith(".pdf"):
                paths.append(os.path.join(root, name))

    return paths


def _load_pdf_parts(paths: list[str]) -> tuple[list[dict], list[str]]:
    pdf_parts = []
    missing_paths = []

    for path in paths:
        if not os.path.exists(path):
            missing_paths.append(path)
            continue
        with open(path, "rb") as f:
            pdf_parts.append({'mime_type': 'application/pdf', 'data': f.read()})

    return pdf_parts, missing_paths


def _clear_uploaded_pdfs() -> int:
    if not os.path.isdir(upload_dir):
        return 0

    deleted_count = 0
    for root, _, files in os.walk(upload_dir):
        for name in files:
            if name.lower().endswith(".pdf"):
                path = os.path.join(root, name)
                try:
                    os.remove(path)
                    deleted_count += 1
                except OSError as e:
                    print(f"刪除失敗: {path}, {e}")

    return deleted_count

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()

    if user_msg in ["使用說明", "help", "Help", "HELP"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=GREETING_MESSAGE))
        return

    if user_msg == "清除檔案":
        deleted_count = _clear_uploaded_pdfs()
        if deleted_count > 0:
            answer = f"已清除 {deleted_count} 份上傳 PDF 來源。"
        else:
            answer = "目前沒有可清除的上傳 PDF。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))
        return

    try:
        paths = _get_pdf_paths()
        pdf_parts, missing_paths = _load_pdf_parts(paths)

        # 所有來源都不存在
        if not pdf_parts:
            answer = "師傅找不到任何 PDF 檔案，請確認 data 資料夾內有放置 .pdf 檔案。"
        else:
            # 【關鍵修正】對齊你的授權清單，使用 2.5 版本
            model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")
            
            source_note = ""
            if missing_paths:
                source_note = f"\n注意：以下資料來源不存在，已略過：{', '.join(missing_paths)}"

            # 呼叫 Gemini 並餵入多份 PDF
            response = model.generate_content(
                pdf_parts
                + [
                    f"你是一位名叫『Edge』的專業老師傅。請綜合所有提供的 PDF 資料回答問題：{user_msg}"
                ]
            )
            answer = response.text
            if source_note:
                answer += source_note

    except Exception as e:
        print(f"!!! 錯誤訊息 !!!: {e}")
        # 備援方案：若 PDF 模式失敗，改用 2.0 版本純文字回答
        try:
            model_alt = genai.GenerativeModel(model_name="models/gemini-2.0-flash")
            res_alt = model_alt.generate_content(f"請以 Edge 身份回答：{user_msg}")
            answer = "(PDF 讀取異常，改由一般模式回答) " + res_alt.text
        except:
            answer = "哎呀，師傅現在腦袋有點卡住，請稍後再問我一次。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))


@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=GREETING_MESSAGE))


@handler.add(MessageEvent, message=FileMessage)
def handle_file_upload(event):
    try:
        file_name = (event.message.file_name or "uploaded.pdf").strip()
        if not file_name.lower().endswith(".pdf"):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="目前只支援上傳 PDF，請傳送 .pdf 檔案。")
            )
            return

        os.makedirs(upload_dir, exist_ok=True)
        safe_name = os.path.basename(file_name)
        save_path = os.path.join(upload_dir, safe_name)

        # 若同名檔案已存在，自動加上流水號避免覆蓋
        if os.path.exists(save_path):
            base, ext = os.path.splitext(safe_name)
            idx = 1
            while True:
                candidate = os.path.join(upload_dir, f"{base}_{idx}{ext}")
                if not os.path.exists(candidate):
                    save_path = candidate
                    break
                idx += 1

        content = line_bot_api.get_message_content(event.message.id)
        with open(save_path, "wb") as f:
            for chunk in content.iter_content():
                f.write(chunk)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"已收到 PDF：{os.path.basename(save_path)}，之後提問會自動納入這份資料。")
        )
    except Exception as e:
        print(f"!!! 檔案上傳處理失敗 !!!: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="PDF 上傳失敗，請稍後再試一次。")
        )

if __name__ == "__main__":
    # 啟動時列出清單，確保連線正常
    print("--- 正在確認模型授權 ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"可使用模型: {m.name}")
    except Exception as e:
        print(f"無法獲取清單: {e}")
    
    app.run(port=5000)
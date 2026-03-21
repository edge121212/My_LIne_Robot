import os
import re
import warnings
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotSdkDeprecatedIn30
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FileMessage
from dotenv import load_dotenv

# LangChain 相關套件
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
app = Flask(__name__)

# 先保留 v2 SDK 寫法，將 v3 deprecation 警告隱藏，避免干擾除錯輸出
warnings.filterwarnings("ignore", category=LineBotSdkDeprecatedIn30)

# LINE 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 1. 初始化 LangChain 與 Gemini
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv('GOOGLE_API_KEY'))
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 確保上傳資料夾存在
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 全局變數存儲向量資料庫
vector_db = None

def load_pdf_to_db(pdf_path):
    """將 PDF 載入到向量資料庫"""
    global vector_db
    try:
        loader = PyPDFLoader(pdf_path)
        data = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=50)
        chunks = text_splitter.split_documents(data)
        
        if vector_db is None:
            vector_db = Chroma.from_documents(
                documents=chunks, 
                embedding=embeddings, 
                persist_directory="./chroma_db"
            )
        else:
            vector_db.add_documents(chunks)
        
        return True
    except Exception as e:
        print(f"Error loading PDF: {e}")
        return False

# 2. 初始化預設 PDF（如果存在）
default_pdf = "data/GA04-GA-basic-1.pdf"
if os.path.exists(default_pdf):
    load_pdf_to_db(default_pdf)
else:
    # 如果沒有 PDF，創建空的向量資料庫
    vector_db = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")

# --- 建立檢索問答鏈 ---
def create_qa_chain():
    template = """請根據以下內容來回答問題：

{context}

問題：{question}"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    retriever = vector_db.as_retriever(search_kwargs={"k": 3})
    
    qa_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return qa_chain


def build_quota_exceeded_message(error_text):
    """將 Gemini 配額錯誤轉成可讀的使用者提示。"""
    retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, re.IGNORECASE)
    if retry_match:
        wait_seconds = int(float(retry_match.group(1))) + 1
        return f"目前 Gemini 配額已用完，請約 {wait_seconds} 秒後再試一次。"
    return "目前 Gemini 配額已用完，請稍後再試，或更換 API Key / 升級方案。"

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
    user_msg = event.message.text
    try:
        if vector_db is None or vector_db._collection.count() == 0:
            answer = "還沒有上傳 PDF，請先上傳 PDF 文件。"
        else:
            qa_chain = create_qa_chain()
            answer = qa_chain.invoke(user_msg)
    except Exception as e:
        print(f"Error: {e}")
        error_text = str(e)
        if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
            answer = build_quota_exceeded_message(error_text)
        else:
            answer = "目前暫時無法回答，請稍後再試。"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))

@handler.add(MessageEvent, message=FileMessage)
def handle_file(event):
    """處理文件上傳"""
    try:
        # 下載文件內容
        message_content = line_bot_api.get_message_content(event.message.id)
        
        # 檢查是否是 PDF
        filename = event.message.file_name
        if not filename.lower().endswith('.pdf'):
            line_bot_api.reply_message(
                event.reply_token, 
                TextSendMessage(text="請上傳 PDF 文件")
            )
            return
        
        # 儲存文件
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, 'wb') as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
        
        # 載入到向量資料庫
        if load_pdf_to_db(file_path):
            answer = f"✅ 已成功載入 PDF：{filename}\n現在可以開始提問了！"
        else:
            answer = f"❌ 無法讀取 PDF：{filename}"
    
    except Exception as e:
        print(f"File handling error: {e}")
        answer = f"處理文件時出錯：{str(e)}"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))

if __name__ == "__main__":
    app.run(port=5000)
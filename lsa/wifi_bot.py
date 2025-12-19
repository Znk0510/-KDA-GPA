import telebot
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

# 路徑設定
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from src.db.database import SessionLocal
from src.db.models import StudentRecord, ConnectionLog, AuthorizationLog

# --- 設定區 ---
API_TOKEN = '8402078101:AAH0NboR53xOwz4LYTMj_Q_PYrypcHq5oQQ'
bot = telebot.TeleBot(API_TOKEN)

user_states = {}
user_data = {}
STATE_WAITING_ID = "WAITING_FOR_STUDENT_ID"
STATE_WAITING_NAME = "WAITING_FOR_NAME"

def get_db():
    return SessionLocal()

# 抓 MAC 函式
def get_mac_address(ip):
    try:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = f"ip neigh show {ip}"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        if "lladdr" in output:
            parts = output.split()
            try:
                return parts[parts.index("lladdr") + 1]
            except: pass
        return "UNKNOWN"
    except: return "UNKNOWN"

# --- 核心：登入/註冊後的處理邏輯 ---
def activate_student_network(db, chat_id, student_record, ip_address):
    try:
        # 1. 寫入連線紀錄
        new_conn = ConnectionLog(
            id=str(uuid.uuid4()),
            mac_address=student_record.mac_address,
            ip_address=ip_address,
            student_id=student_record.student_id,
            status="connected",
            timestamp=datetime.now(timezone.utc)
        )
        db.add(new_conn)

        # 2. 寫入授權紀錄
        new_auth = AuthorizationLog(
            id=str(uuid.uuid4()),
            mac_address=student_record.mac_address,
            status="active",
            authorized_at=datetime.now(timezone.utc),
            details={"source": "telegram_bot", "chat_id": chat_id}
        )
        db.add(new_auth)
        
        # === ### 修改處 START: 使用 update() 強制寫入 ===
        print(f"[Debug] 正在將學生 {student_record.student_id} 更新為 online")
        
        # 直接對資料庫下指令，不依賴物件狀態
        db.query(StudentRecord).\
            filter(StudentRecord.student_id == student_record.student_id).\
            update({"status": "online"})
            
        # === ### 修改處 END ===

        db.commit() # 這裡送出交易
        print("[Debug] 資料庫 Commit 完成")

        # 4. 執行 Linux 開網指令
        subprocess.run(["sudo", "LSA/login.sh", ip_address])
        
        bot.send_message(chat_id, "✅ 網路已開通！狀態已更新為 Online。\n請切回 Wi-Fi 使用。")
        
    except Exception as e:
        print(f"[Activation Error] {e}")
        db.rollback() # 如果出錯，所有變更(包含上面的 update)都會被取消
        bot.send_message(chat_id, "⚠️ 開通失敗，請聯繫管理員。")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    try:
        # 這裡有簡單防呆，避免 split 失敗
        args = message.text.split()
        if len(args) > 1:
            user_ip = args[1].replace("_", ".")
        else:
            bot.reply_to(message, "⚠️ 請透過登入頁面按鈕開啟機器人 (缺少 IP 參數)。")
            return
    except IndexError:
        bot.reply_to(message, "⚠️ 參數錯誤。")
        return

    db = get_db()
    try:
        student = db.query(StudentRecord).filter(StudentRecord.telegram_id == str(chat_id)).first()

        if student:
            bot.reply_to(message, f"歡迎回來，{student.name}！\n正在開通網路...")
            
            # 更新 MAC (防止換手機)
            current_mac = get_mac_address(user_ip)
            if current_mac != "UNKNOWN" and current_mac != student.mac_address:
                student.mac_address = current_mac
                # 這裡不用 commit，因為下面 activate_student_network 會統一 commit
            
            activate_student_network(db, chat_id, student, user_ip)
        else:
            user_data[chat_id] = {"ip": user_ip}
            user_states[chat_id] = STATE_WAITING_ID
            bot.reply_to(message, "👋 初次見面！請輸入您的 **學號**：")
    finally:
        db.close()

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_states.get(chat_id)
    db = get_db()

    try:
        if state == STATE_WAITING_ID:
            user_data[chat_id]["student_id"] = text
            user_states[chat_id] = STATE_WAITING_NAME
            bot.reply_to(message, "收到，請輸入您的 **真實姓名**：")

        elif state == STATE_WAITING_NAME:
            name = text
            student_id = user_data[chat_id]["student_id"]
            ip = user_data[chat_id]["ip"]
            mac = get_mac_address(ip)

            if mac == "UNKNOWN":
                bot.reply_to(message, "⚠️ 無法抓取 MAC 位址，請確認連線後重新點擊連結。")
                return

            # 建立新學生資料 (預設 offline，馬上就會被改成 online)
            new_student = StudentRecord(
                id=str(uuid.uuid4()),
                student_id=student_id,
                name=name,
                mac_address=mac,
                telegram_id=str(chat_id),
                p_status='NORMAL',
                status='offline' # 初始建立
            )
            db.add(new_student)
            # 這裡先 commit 產生 ID，後續函式再 update status
            db.commit() 
            
            bot.reply_to(message, f"註冊成功！{name} ({student_id})")
            
            # 呼叫開通函式 (這裡面會把 status 改成 online)
            activate_student_network(db, chat_id, new_student, ip)

            # 清理狀態
            del user_states[chat_id]
            del user_data[chat_id]
            
    except Exception as e:
        print(f"[Error] {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🤖 Telegram Bot 啟動中...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot 停止運作: {e}")
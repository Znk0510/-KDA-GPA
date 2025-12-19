import os
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()


# --- 設定區 ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
PAYMENT_PROVIDER_TOKEN = "" 

# 設置解鎖的目標 IP，這必須與 simulation.py 中的 TARGET_IP 相同
TARGET_PHONE_IP = "192.168.100.1" 

# 設定 Log 格式
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kda_bot")

if not BOT_TOKEN:
    raise ValueError("❌ 錯誤: 未設定 BOT_TOKEN，請檢查 .env 檔案")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- 輔助函式：通知後端 ---
async def notify_backend(action: str, payload: dict):
    url = f"{BACKEND_API_URL}/api/{action}"
    logger.info(f"📡 正在呼叫後端: {url} | Data: {payload}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    logger.info("✅ 後端回應成功")
                    return True, await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"❌ 後端回應錯誤 ({resp.status}): {text}")
                    return False, text
    except Exception as e:
        logger.error(f"🔥 連線失敗: {e}")
        return False, str(e)

# --- 指令處理 ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    """
    處理 /start 指令，包含 Deep Link (轉盤跳轉)
    """
    args = command.args
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    # 情況 A: 帶有 Deep Link 參數 (例如 start=pay_50) -> 進入付款模式
    if args and args.startswith("undefined_"):
        try:
            amount_str = args.split("_")[1]
            amount = int(amount_str)
            
            logger.info(f"💰 收到繳費請求: 用戶 {user_name} ({user_id}), 金額 {amount}")

            # 發送發票 (Invoice)
            await bot.send_invoice(
                chat_id=message.chat.id,
                title="KDA 違規罰款",
                description=f"依據課堂規則，需支付 {amount} 星星以解鎖網路。",
                payload=str(user_id), 
                provider_token=PAYMENT_PROVIDER_TOKEN,
                currency="XTR", 
                prices=[LabeledPrice(label="違規罰金", amount=amount)],
                start_parameter=f"undefined_{amount}"
            )
            return

        except Exception as e:
            logger.error(f"解析付款參數失敗: {e}")
            await message.answer("❌ 連結參數錯誤，無法產生帳單。")
            return

    # 情況 B: 沒有參數 (直接輸入 /start) -> 顯示 Demo 控制台 (老師模式)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔒 [老師] 測試封鎖", callback_data="demo_block")
    kb.button(text="❓ 查詢狀態", callback_data="check_status")
    kb.adjust(1)
    
    await message.answer(
        f"👋 哈囉 {user_name}！\n我是 KDA 智慧教室助理。\n\n如果是被轉盤導向過來，請重新點擊網頁上的按鈕",
        reply_markup=kb.as_markup()
    )

# --- 支付流程 ---

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """
    付款前的確認 (必須在 10 秒內回應 ok=True)
    """
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    """
    付款成功後的處理
    """
    payment = message.successful_payment
    total_amount = payment.total_amount
    
    logger.info(f"✅ 付款成功! 用戶準備解鎖 IP: {TARGET_PHONE_IP}, 金額: {total_amount}")

    await message.answer(f"🎉 <b>收到 {total_amount} 星星！</b>\n系統正在通知伺服器為您解鎖...", parse_mode="HTML")

    # 1. 通知後端 API 解鎖
    # ⚠️ 這裡直接將 TARGET_PHONE_IP 傳入，繞過 UserID -> IP 映射
    success, resp = await notify_backend("payment/callback", {
        "student_id": TARGET_PHONE_IP, # 將 IP 作為 student_id 傳入
        "payment_id": payment.telegram_payment_charge_id,
        "amount": total_amount
    })

    if success:
        await message.answer(f"✅ <b>IP {TARGET_PHONE_IP} 網路已恢復！</b>\n您可以關閉此視窗並重新整理網頁。", parse_mode="HTML")
    else:
        await message.answer(f"⚠️ <b>付款成功但解鎖失敗</b>\n請聯繫老師。\n錯誤: {resp}", parse_mode="HTML")

# --- Demo 按鈕回調 ---

@dp.callback_query(F.data == "demo_block")
async def cb_demo_block(callback: types.CallbackQuery):
    """
    老師按「測試封鎖」: 僅顯示訊息，不再呼叫可能導致 Bot 自身斷網的 API
    """
    user_id = str(callback.from_user.id)
    # ⚠️ 這裡直接使用我們設定的手機 IP 作為目標，但不執行封鎖。
    test_ip = TARGET_PHONE_IP 
    
    # 顯示訊息給老師，假裝正在執行封鎖
    await callback.message.edit_text(
        f"✅ <b>[Demo] 模擬封鎖成功！</b>\n"
        f"🚫 已向 Server 發送封鎖指令，目標 IP: <code>{test_ip}</code>\n"
        f"請確認目標裝置({test_ip})是否已斷網，並引導使用者進入繳費流程。",
        parse_mode="HTML"
    )
    
    await callback.answer("已模擬執行封鎖指令。", show_alert=True)
@dp.callback_query(F.data == "check_status")
async def cb_check_status(callback: types.CallbackQuery):
    await callback.answer("功能開發中...", show_alert=True)

# --- 啟動點 ---
if __name__ == "__main__":
    print("🤖 KDA Bot (Aiogram 版) 啟動中...")
    asyncio.run(dp.start_polling(bot))

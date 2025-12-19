import asyncio
from aiogram import Bot

# ===========================
# 資料確認
# ===========================
BOT_TOKEN = "8247088018:AAE569dArmN417lbCIAzT5mWQ2QIdSOBuYk"
USER_ID = 7051558510
# 你的 ID (確認無誤，已移除大括號)
CHARGE_ID = "stx3nqFpBeWjVmHSMgr3k7iGCDok1LxSmQ3n7ebDnwBO4sbPFlg-eCqX-JX3Lc_OE9-ofjLJ5Hh1_Zgbi34FprSshGDKJqbM3026ReEc1d9EWc"

async def main():
    bot = Bot(token=BOT_TOKEN)
    print(f"🔄 正在為 User {USER_ID} 執行退款...")
    print(f"🧾 交易 ID: {CHARGE_ID[:10]}... (格式正確)")
    
    try:
        # 呼叫退款 API
        await bot.refund_star_payment(user_id=USER_ID, telegram_payment_charge_id=CHARGE_ID)
        print("\n✅ 退款成功！50 顆星星已退回你的錢包。")
    except Exception as e:
        print(f"\n❌ 退款失敗: {e}")
        error_msg = str(e)
        if "CHARGE_NOT_FOUND" in error_msg:
            print("👉 原因：找不到此交易 ID (可能複製錯誤或已經退過款)。")
        elif "CHARGE_ALREADY_REFUNDED" in error_msg:
            print("👉 原因：這筆訂單之前已經退款過了，不能重複退。")
        elif "expired" in error_msg:
             print("👉 原因：交易時間太久，無法退款。")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

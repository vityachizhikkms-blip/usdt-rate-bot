"""
Telegram-бот для отображения актуального курса USDT
- P2P Bybit (USDT/RUB)
- HTX (USDT/CNY)
"""

import os
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8712960938:AAEQYnf-ITCx3vYjD4-fPL0vDyglF0H0xFE")


def get_bybit_p2p_rate(token="USDT", currency_id="RUB", rows=5):
    url = "https://api2.bybit.com/fiat/otc/item/online"
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    results = {}
    for s, label in [("1", "buy"), ("0", "sell")]:
        payload = {"userId": "", "tokenId": token, "currencyId": currency_id,
                   "payment": [], "side": s, "size": str(rows), "page": "1", "amount": ""}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            items = data.get("result", {}).get("items", [])
            results[label] = float(items[0]["price"]) if items else None
        except Exception as e:
            logger.error(f"Bybit P2P error (side={s}): {e}")
            results[label] = None
    return results


def get_htx_usdt_cny():
    for pair in ["usdtcnyt", "usdthusd"]:
        try:
            url = f"https://api.htx.com/market/detail/merged?symbol={pair}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == "ok":
                tick = data["tick"]
                return {"pair": pair.upper(), "price": tick.get("close"),
                        "high": tick.get("high"), "low": tick.get("low")}
        except Exception as e:
            logger.error(f"HTX ticker error ({pair}): {e}")
    try:
        url = "https://otc-api.htx.com/v1/data/trade-market"
        params = {"coinId": 2, "currency": 1, "tradeType": "buy", "currPage": 1,
                  "payMethod": 0, "acceptOrder": 0, "blockType": "general",
                  "online": 1, "range": 0, "amount": ""}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("list", [])
        if items:
            return {"pair": "USDT/CNY (OTC)", "price": float(items[0]["price"]), "high": None, "low": None}
    except Exception as e:
        logger.error(f"HTX OTC error: {e}")
    return None


def build_rates_message():
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    lines = [f"📊 <b>Актуальный курс USDT</b>", f"🕐 {now}\n"]
    lines.append("🔵 <b>Bybit P2P (USDT/RUB)</b>")
    try:
        bybit = get_bybit_p2p_rate()
        buy, sell = bybit.get("buy"), bybit.get("sell")
        lines.append(f"  Покупка:  <code>{buy:.2f} ₽</code>" if buy else "  Покупка: нет данных")
        lines.append(f"  Продажа: <code>{sell:.2f} ₽</code>" if sell else "  Продажа: нет данных")
        if buy and sell:
            lines.append(f"  Спред: <code>{abs(buy - sell):.2f} ₽</code>")
    except Exception as e:
        lines.append(f"  ⚠️ Ошибка: {e}")
    lines.append("")
    lines.append("🟡 <b>HTX (USDT/CNY)</b>")
    try:
        htx = get_htx_usdt_cny()
        if htx and htx.get("price"):
            lines.append(f"  Цена: <code>{htx['price']:.4f} ¥</code>")
            if htx.get("high"):
                lines.append(f"  Макс (24ч): <code>{htx['high']:.4f} ¥</code>")
            if htx.get("low"):
                lines.append(f"  Мин (24ч): <code>{htx['low']:.4f} ¥</code>")
            lines.append(f"  Пара: {htx['pair']}")
        else:
            lines.append("  ⚠️ Нет данных")
    except Exception as e:
        lines.append(f"  ⚠️ Ошибка: {e}")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💹 Получить курс", callback_data="get_rates")]]
    await update.message.reply_text(
        "👋 Привет! Я бот для отслеживания курса USDT.\n\nНажми кнопку или /rates:",
        reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Загружаю данные...")
    keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data="get_rates")]]
    await msg.edit_text(build_rates_message(), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_get_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Обновляю данные...")
    keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data="get_rates")]]
    try:
        await query.edit_message_text(build_rates_message(), parse_mode="HTML",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>Команды:</b>\n/start — приветствие\n/rates — курс USDT\n/help — справка\n\n"
        "• <b>Bybit P2P</b> — USDT/RUB\n• <b>HTX</b> — USDT/CNY", parse_mode="HTML")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("rates", cmd_rates))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(callback_get_rates, pattern="^get_rates$"))
    print("🤖 Бот запущен.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

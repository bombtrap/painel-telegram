import os
import asyncio
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url_painel = "https://bombtrap.github.io/painel-telegram/?v=2"
    keyboard = [[InlineKeyboardButton(text="📊 Abrir Painel de Radares", web_app=WebAppInfo(url=url_painel))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Olá! Clique no botão abaixo para gerenciar seus radares:", reply_markup=reply_markup)

async def listar_radares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT id, chat_id, origem, destino, data_partida, preco_alvo, margem, alerta_madrugada FROM radares")
        linhas = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not linhas:
            await update.message.reply_text("📭 O banco de dados está vazio!")
            return
            
        mensagem = "🗄️ *RADARES SALVOS EM NUVEM (NEON):*\n\n"
        for r_id, chat_id, origem, destino, data, preco_alvo, margem, alerta in linhas:
            teto = preco_alvo * (1 + (margem / 100))
            mensagem += (
                f"🆔 *ID:* {r_id}\n"
                f"👤 *User:* `{chat_id}`\n"
                f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                f"📅 *Data:* {data}\n"
                f"💵 *Preço Alvo:* R$ {preco_alvo:.2f} (Teto: R$ {teto:.2f})\n"
                f"🚨 *Despertador:* {alerta}\n"
                f"-------------------------\n"
            )
        await update.message.reply_text(mensagem, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler banco: {e}")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar", listar_radares))
    app.run_polling()

if __name__ == "__main__":
    main()
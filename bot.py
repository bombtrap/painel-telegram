import os
import asyncio
import psycopg2 # Mudamos para psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url_painel = "https://bombtrap.github.io/painel-telegram/"
    keyboard = [[InlineKeyboardButton(text="📊 Abrir Painel de Radares", web_app=WebAppInfo(url=url_painel))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Olá! Clique no botão abaixo para gerenciar seus radares:", reply_markup=reply_markup)

async def listar_radares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS radares (
                id SERIAL PRIMARY KEY,
                chat_id TEXT,
                origem TEXT,
                destino TEXT,
                preco_maximo DOUBLE PRECISION
            )
        ''')
        cursor.execute("SELECT id, chat_id, origem, destino, preco_maximo FROM radares")
        linhas = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not linhas:
            await update.message.reply_text("📭 O banco de dados está vazio!")
            return
            
        mensagem = "🗄️ *RADARES SALVOS EM NUVEM (NEON):*\n\n"
        for id_radar, chat_id, origem, destino, preco_maximo in linhas:
            mensagem += (
                f"🆔 *ID:* {id_radar}\n"
                f"👤 *User:* `{chat_id}`\n"
                f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                f"💵 *Teto:* R$ {preco_maximo:.2f}\n"
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
import os
import asyncio
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== CONFIGURAÇÕES VIA SISTEMA ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_NAME = "radares.db"
# =====================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao comando /start com o botão do Painel WebApp"""
    url_painel = "https://bombtrap.github.io/painel-telegram/"
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 Abrir Painel de Radares", 
                web_app=WebAppInfo(url=url_painel)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Olá! Este é o seu caçador privado de passagens.\n\n"
        "Clique no botão abaixo para gerenciar os seus radares de voo:",
        reply_markup=reply_markup
    )


def main():
    print("🤖 Inicializando o processo do Bot...")
    
    # 🔥 CORREÇÃO DEFINITIVA PARA PYTHON 3.12+ / 3.14 NO RENDER:
    # Criamos e definimos o loop na linha principal antes do Telegram iniciar.
    # Isso impede o "RuntimeError: There is no current event loop".
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Cria a aplicação oficial do Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Registra o comando /start
    app.add_handler(CommandHandler("start", start))
    
    print("🟩 Bot pronto e aguardando conexões!")
    
    # O run_polling nativo gerencia quedas de rede e CancelledError automaticamente
    app.run_polling()


if __name__ == "__main__":
    main()
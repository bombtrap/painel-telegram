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


async def listar_radares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando secreto para listar todos os radares salvos no banco de dados SQLite"""
    print("🔍 Comando /listar acionado por um usuário.")
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Garante que a tabela existe antes de ler
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS radares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                origem TEXT,
                destino TEXT,
                preco_maximo REAL
            )
        ''')
        
        cursor.execute("SELECT id, chat_id, origem, destino, preco_maximo FROM radares")
        linhas = cursor.fetchall()
        conn.close()
        
        if not linhas:
            await update.message.reply_text("📭 O banco de dados está vazio. Nenhum radar cadastrado ainda!")
            return
            
        # Monta a mensagem listando o que achou no DB
        mensagem = "🗄️ *RADARES CADASTRADOS NO BANCO:*\n\n"
        for id_radar, chat_id, origem, destino, preco_maximo in linhas:
            mensagem += (
                f"🆔 *ID:* {id_radar}\n"
                f"👤 *User Chat ID:* `{chat_id}`\n"
                f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                f"💵 *Teto:* R$ {preco_maximo:.2f}\n"
                f"-------------------------\n"
            )
            
        await update.message.reply_text(mensagem, parse_mode="Markdown")
        
    except Exception as e:
        print(f"❌ Erro ao ler o banco de dados: {e}")
        await update.message.reply_text("❌ Erro interno ao tentar acessar o banco de dados.")


def main():
    print("🤖 Inicializando o processo do Bot...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Registro dos comandos do bot
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar", listar_radares)) # <-- Novo comando cadastrado aqui!
    
    print("🟩 Bot pronto e aguardando conexões!")
    app.run_polling()


if __name__ == "__main__":
    main()
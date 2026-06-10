import json
import os  # <-- Adicionamos essa linha para o Python conseguir ler o sistema
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURAÇÕES VIA SISTEMA ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
URL_DO_FORMULARIO = "https://bombtrap.github.io/painel-telegram/"
# ===================================================================

# ================= BANCO DE DADOS ALINHADO =================
def iniciar_banco():
    conn = sqlite3.connect("radares.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radares (
            user_id INTEGER,
            origem TEXT,
            destino TEXT,
            alternativo TEXT,
            max_paradas INTEGER,
            skip_alternativa TEXT,
            data_partida TEXT,
            hora_min TEXT,
            hora_max TEXT,
            preco_alvo REAL,
            margem INTEGER,
            alerta_madrugada TEXT,
            telefone TEXT
        )
    """)
    conn.commit()
    conn.close()

def salvar_radar(user_id, c):
    conn = sqlite3.connect("radares.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM radares WHERE user_id = ?", (user_id,))
    cursor.execute("""
        INSERT INTO radares VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, c['origem'], c['destino'], c['alternativo'], c['maxParadas'], 
          c['skipAlternativa'], c['dataPartida'], c['horaMin'], c['horaMax'], 
          c['precoAlvo'], c['margem'], c['alertaMadrugada'], c['telefone']))
    conn.commit()
    conn.close()
# =============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    
    # Texto atualizado conforme solicitado por você!
    texto = (
        f"Olá, {user_name}! ✈️\n\n"
        f"Aperte o botão abaixo para configurar o seu painel de buscas privado. "
        f"As ofertas encontradas serão enviadas diretamente para o seu privado."
    )
    
    botao_painel = KeyboardButton(text="⚙️ Abrir Painel de Controle", web_app=WebAppInfo(url=URL_DO_FORMULARIO))
    teclado = ReplyKeyboardMarkup([[botao_painel]], resize_keyboard=True)
    await update.message.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")

async def receber_dados_painel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa o retorno do Mini App e envia o resumo privado"""
    user_id = update.effective_user.id
    dados_brutos = update.message.web_app_data.data
    config = json.loads(dados_brutos)
    
    # Salva vinculando ao ID privado do usuário
    salvar_radar(user_id, config)
    
    teto_com_margem = config['precoAlvo'] * (1 + (config['margem'] / 100))
    link_google_flights = f"https://www.google.com/travel/flights?q=Flights%20to%20{config['destino']}%20from%20{config['origem']}%20on%20{config['dataPartida']}"

    # Dicionário de tradução corrigido (Com Pushover incluso!)
    traducao_alerta = {
        "telegram": "💬 Mensagem de texto privada aqui no Telegram",
        "ligacao": f"📞 Ligação Telefônica Real no número ({config['telefone']})",
        "pushover": "📢 Alerta de Sirene (Bypass Não Perturbe) via Pushover"
    }
    alerta_escolhido = traducao_alerta.get(config['alertaMadrugada'], "Não definido")

    # Linha do destino alternativo corrigida e validada
    destino_alt_txt = config['alternativo'] if config['alternativo'] else "Nenhum"

    resposta = (
        f"✅ *Radar Configurado com Sucesso!*\n\n"
        f"🛫 *Origem:* {config['origem']}\n"
        f"🛬 *Destino Principal:* {config['destino']}\n"
        f"🔄 *Destino Alternativo:* {destino_alt_txt}\n"
        f"💵 *Preço Alvo:* R$ {config['precoAlvo']:.2f} (Alerta máximo até: R$ {teto_com_margem:.2f})\n"
        f"📅 *Data:* {config['dataPartida']}\n\n"
        f"🔔 *Estratégia de Madrugada:* \n`{alerta_escolhido}`\n\n"
        f"🔗 [Acompanhar voo manualmente no Google Flights]({link_google_flights})\n\n"
        f"_*Rastreamento privado ativado de forma exclusiva para você!*_"
    )
    
    await update.message.reply_text(resposta, parse_mode="Markdown", disable_web_page_preview=True)

async def iniciar_bot():
    # Toda a lógica que estava no seu antigo def main() entra aqui:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Seus comandos (start, etc) e handlers continuam aqui:
    # app.add_handler(CommandHandler("start", start))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Mantém o bot vivo rodando
    while True:
        await asyncio.sleep(3600)

def main():
    import asyncio
    # O asyncio.run cria e gerencia o loop automaticamente do jeito que o Python 3.14 exige
    asyncio.run(iniciar_bot())

if __name__ == "__main__":
    main()
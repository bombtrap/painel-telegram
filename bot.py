import os
import re
import telebot
import psycopg2
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TUNNEL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8080")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def enviar_boas_vindas(message):
    nome = message.from_user.first_name
    texto = (
        f"👋 Fala, {nome}! Bem-vindo ao *Motor de Busca de Passagens*.\n\n"
        f"Eu sou um robô rastreador. Fico monitorando a malha aérea 24 horas por dia em busca de tarifas ocultas e quedas de preço.\n\n"
        f"🤖 *Central de Comando:*\n"
        f"📌 `/novo` - Abre o painel seguro para cadastrar um novo radar.\n"
        f"📋 `/radares` - Lista e gerencia todas as suas buscas ativas.\n"
        f"❓ `/comandos` - Exibe este menu novamente."
    )
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['start', 'help', 'comandos'])
def comando_ajuda(message):
    enviar_boas_vindas(message)

@bot.message_handler(func=lambda message: message.text and re.search(r'\b(oi|ol[aá]|eae|e a[ií]|opa|bom dia|boa tarde|boa noite|salve)\b', message.text.lower()))
def saudacao_livre(message):
    enviar_boas_vindas(message)

@bot.message_handler(commands=['novo'])
def abrir_painel(message):
    url_final = TUNNEL_URL if TUNNEL_URL.endswith("/") else f"{TUNNEL_URL}/"
    markup = InlineKeyboardMarkup()
    botao = InlineKeyboardButton(
        text="🎛️ Configurar Novo Radar Otimizado", 
        web_app=telebot.types.WebAppInfo(url=url_final)
    )
    markup.add(botao)
    bot.send_message(message.chat.id, "💡 Clique abaixo para carregar o painel modular:", reply_markup=markup)

@bot.message_handler(commands=['radares'])
def listar_radares(message):
    chat_id = str(message.chat.id)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, origem, destino, alternativo, 
                   skip_principal, paradas_principal, 
                   skip_alternativa, max_paradas, 
                   datas_flexiveis, dias_antes, dias_depois,
                   preco_alvo, data_partida 
            FROM radares 
            WHERE chat_id = %s ORDER BY id DESC
        """, (chat_id,))
        linhas = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao acessar o Neon: {e}")
        return

    if not linhas:
        bot.send_message(message.chat.id, "📭 Você não possui nenhum radar ativo. Use `/novo`.")
        return

    bot.send_message(message.chat.id, f"📋 *Você possui {len(linhas)} radar(es) ativos:*", parse_mode="Markdown")
    
    url_base = TUNNEL_URL if TUNNEL_URL.endswith("/") else f"{TUNNEL_URL}/"
    
    for r_id, origem, destino, alternativo, skip_p, paradas_p, skip_a, max_p, flex_ok, d_antes, d_depois, preco_alvo, data_partida in linhas:
        markup = InlineKeyboardMarkup()
        url_edit = f"{url_base}?edit_id={r_id}"
        
        botao_editar = InlineKeyboardButton(text="✏️ Editar", web_app=telebot.types.WebAppInfo(url=url_edit))
        botao_excluir = InlineKeyboardButton(text="🗑️ Excluir", callback_data=f"del_{r_id}")
        markup.row(botao_editar, botao_excluir)
        
        card = (
            f"📍 *Radar #{r_id}*\n"
            f"🛫 *Origem:* {origem}   *Destino:* {destino}\n"
            f"   ┗ 💥 *Skip Principal:* {'Sim' if skip_p == 'sim' else 'Não'} | *Paradas:* {paradas_p}\n"
        )
        if alternativo and alternativo.strip():
            card += f"   ┗ 🚌 *Skip Alternativo:* {'Sim' if skip_a == 'sim' else 'Não'} | *Paradas:* {max_p}\n"
            
        card += f"📅 *Data:* {data_partida}\n"
        
        if flex_ok:
            card += f"   ┗ 📅 *Datas Flexíveis:* -{d_antes}d / +{d_depois}d\n"
            
        card += f"💵 *Alvo:* R$ {preco_alvo:.2f}\n"
            
        bot.send_message(message.chat.id, card, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def deletar_radar_callback(call):
    radar_id = int(call.data.split('_')[1])
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM radares WHERE id = %s", (radar_id,))
        conn.commit()
        cursor.close()
        conn.close()
        bot.answer_callback_query(call.id, text="Radar removido!")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=f"🗑️ _Radar #{radar_id} removido._", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Falha ao excluir o radar: {e}")

if __name__ == "__main__":
    bot.infinity_polling()
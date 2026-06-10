import os
import time
import sqlite3
import requests
from datetime import datetime
from twilio.rest import Client

# ==================== CONFIGURAÇÕES VIA SISTEMA ====================
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMERO = os.getenv("TWILIO_NUMERO")
# =====================================================================

DB_NAME = "radares.db"

def disparar_ligacao_twilio():
    """Faz a chamada telefônica via Twilio para avisar sobre a passagem na madrugada"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        destino_ligacao = os.getenv("TWILIO_NUMERO_DESTINO", TWILIO_NUMERO) 
        
        mensagem_twiml = (
            '<Response>'
            '<Say language="pt-BR" voice="alice">'
            'Atenção! Uma das passagens configuradas no seu radar foi encontrada! Verifique o Telegram!'
            '</Say>'
            '</Response>'
        )
        
        call = client.calls.create(
            twiml=mensagem_twiml,
            to=destino_ligacao,
            from_=TWILIO_NUMERO
        )
        print(f"📞 Ligação disparada com sucesso! SID: {call.sid}")
    except Exception as e:
        print(f"❌ Erro ao disparar ligação Twilio: {e}")


def enviar_alerta_telegram(chat_id, mensagem):
    """Envia mensagem de texto formatada para o usuário específico no Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"❌ Erro ao enviar Telegram: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha de conexão ao enviar Telegram: {e}")


def pesquisar_passagens_travelpayouts(origem, destino):
    """Consulta a API da Travelpayouts em busca dos preços mais recentes em cache"""
    url = "https://api.travelpayouts.com/v2/prices/latest"
    headers = {"X-Access-Token": TRAVELPAYOUTS_TOKEN}
    
    params = {
        "origin": origem,
        "destination": destino,
        "currency": "BRL",
        "period_type": "year",
        "page": 1,
        "limit": 5,
        "show_to_affiliates": "true",
        "sorting": "price"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            dados = response.json()
            if dados.get("success") and dados.get("data"):
                return dados["data"]
        else:
            print(f"❌ Erro na Travelpayouts: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha na requisição da passagem: {e}")
    return []


def executar_varredura():
    """Varre apenas os radares cadastrados por você e seus amigos"""
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura dos radares ativos...")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS radares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            origem TEXT,
            destino TEXT,
            preco_maximo REAL
        )
    ''')
    conn.commit()
    
    # Busca estritamente o que foi inserido via painel/bot
    cursor.execute("SELECT chat_id, origem, destino, preco_maximo FROM radares")
    radares_usuarios = cursor.fetchall()
    
    for chat_id, origem, destino, preco_maximo in radares_usuarios:
        voos = pesquisar_passagens_travelpayouts(origem, destino)
        
        for voo in voos:
            preco_real = voo.get("value")
            if preco_real and preco_real <= preco_maximo:
                msg = (
                    f"🚨 *RADAR DISPARADO!*\n\n"
                    f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                    f"💵 *Preço encontrado:* R$ {preco_real:.2f}\n"
                    f"🎯 *Seu limite:* R$ {preco_maximo:.2f}\n"
                    f"📅 *Data de Ida:* {voo.get('depart_date')}\n\n"
                    f"🔗 _Acesse o painel para garantir a emissão!_"
                )
                # Envia a mensagem exatamente para o amigo (chat_id) que criou o radar
                enviar_alerta_telegram(chat_id, msg)
                
                # Alerta sonoro por telefone se for de madrugada
                hora_atual = datetime.now().hour
                if 0 <= hora_atual <= 6:
                    disparar_ligacao_twilio()
                break
        time.sleep(1.5)

    conn.close()
    print("💤 Varredura concluída. Aguardando próximo ciclo de 30 minutos...")


if __name__ == "__main__":
    print("🕵️‍♂️ Motor do Scraper Privado Inicializado!")
    while True:
        try:
            executar_varredura()
        except Exception as e:
            print(f"❌ Erro crítico no loop: {e}")
        time.sleep(1800)
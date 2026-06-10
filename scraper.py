import os
import time
import psycopg2 # Mudamos para psycopg2
import requests
from datetime import datetime
from twilio.rest import Client

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMERO = os.getenv("TWILIO_NUMERO")

def disparar_ligacao_twilio():
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        destino_ligacao = os.getenv("TWILIO_NUMERO_DESTINO", TWILIO_NUMERO) 
        mensagem_twiml = '<Response><Say language="pt-BR" voice="alice">Radar disparado! Verifique o Telegram!</Say></Response>'
        client.calls.create(twiml=mensagem_twiml, to=destino_ligacao, from_=TWILIO_NUMERO)
    except Exception as e:
        print(f"❌ Erro Twilio: {e}")

def enviar_alerta_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
    except:
        pass

def pesquisar_passagens_travelpayouts(origem, destino):
    url = "https://api.travelpayouts.com/v2/prices/latest"
    headers = {"X-Access-Token": TRAVELPAYOUTS_TOKEN}
    params = {"origin": origem, "destination": destino, "currency": "BRL", "period_type": "year", "page": 1, "limit": 5, "show_to_affiliates": "true", "sorting": "price"}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            dados = response.json()
            if dados.get("success") and dados.get("data"):
                return dados["data"]
    except:
        pass
    return []

def executar_varredura():
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Varrendo banco em nuvem...")
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
    conn.commit()
    
    cursor.execute("SELECT chat_id, origem, destino, preco_maximo FROM radares")
    radares_usuarios = cursor.fetchall()
    
    for chat_id, origem, destino, preco_maximo in radares_usuarios:
        voos = pesquisar_passagens_travelpayouts(origem, destino)
        for voo in voos:
            preco_real = voo.get("value")
            if preco_real and preco_real <= preco_maximo:
                msg = f"🚨 *RADAR DISPARADO!*\n\n✈️ *Rota:* {origem} ➡️ {destino}\n💵 *Preço:* R$ {preco_real:.2f}\n🎯 *Seu limite:* R$ {preco_maximo:.2f}"
                enviar_alerta_telegram(chat_id, msg)
                if 0 <= datetime.now().hour <= 6:
                    disparar_ligacao_twilio()
                break
        time.sleep(1.5)
    cursor.close()
    conn.close()

if __name__ == "__main__":
    while True:
        try:
            executar_varredura()
        except Exception as e:
            print(f"❌ Erro loop: {e}")
        time.sleep(1800)
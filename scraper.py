import os
import time
import psycopg2
import requests
from datetime import datetime
from twilio.rest import Client

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMERO = os.getenv("TWILIO_NUMERO")

def disparar_ligacao_twilio(telefone_usuario):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        destino = telefone_usuario if telefone_usuario else os.getenv("TWILIO_NUMERO_DESTINO")
        if not destino: return
        
        mensagem_twiml = '<Response><Say language="pt-BR" voice="alice">Radar disparado! Verifique o Telegram!</Say></Response>'
        client.calls.create(twiml=mensagem_twiml, to=destino, from_=TWILIO_NUMERO)
        print(f"📞 [Twilio] Ligacao telefonica efetuada para {destino}")
    except Exception as e:
        print(f"❌ Erro Twilio: {e}")

def enviar_alerta_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"})
    except: pass

def pesquisar_passagens_travelpayouts(origem, destino):
    url = "https://api.travelpayouts.com/v2/prices/latest"
    headers = {"X-Access-Token": TRAVELPAYOUTS_TOKEN}
    params = {"origin": origem, "destination": destino, "currency": "BRL", "period_type": "year", "page": 1, "limit": 5, "show_to_affiliates": "true", "sorting": "price"}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            dados = response.json()
            if dados.get("success") and dados.get("data"): return dados["data"]
    except: pass
    return []

def executar_varredura():
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura no Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT chat_id, origem, destino, preco_alvo, margem, alerta_madrugada, telefone FROM radares")
    radares_usuarios = cursor.fetchall()
    
    for chat_id, origem, destino, preco_alvo, margem, alerta_madrugada, telefone in radares_usuarios:
        voos = pesquisar_passagens_travelpayouts(origem, destino)
        teto_maximo = preco_alvo * (1 + (margem / 100))
        
        for voo in voos:
            preco_real = voo.get("value")
            if preco_real and preco_real <= teto_maximo:
                msg = (
                    f"🚨 *RADAR DISPARADO!*\n\n"
                    f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                    f"💵 *Preço Encontrado:* R$ {preco_real:.2f}\n"
                    f"🎯 *Seu Limite Máximo:* R$ {teto_maximo:.2f}"
                )
                enviar_alerta_telegram(chat_id, msg)
                
                # Se for madrugada e configurou ligacao, o Twilio entra em acao
                if 0 <= datetime.now().hour <= 6 and alerta_madrugada == "ligacao":
                    disparar_ligacao_twilio(telefone)
                break
        time.sleep(1.5)
    cursor.close()
    conn.close()

if __name__ == "__main__":
    while True:
        try: executar_varredura()
        except Exception as e: print(f"❌ Erro loop scraper: {e}")
        time.sleep(1800)
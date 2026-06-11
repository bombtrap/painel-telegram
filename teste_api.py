import os
import time
import psycopg2
import requests
from datetime import datetime
from twilio.rest import Client

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMERO = os.getenv("TWILIO_NUMERO")

def disparar_ligacao_twilio(telefone_usuario):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        destino = telefone_usuario if telefone_usuario else os.getenv("TWILIO_NUMERO_DESTINO")
        if not destino: 
            print("⚠️ [Twilio] Nenhum numero de destino configurado.")
            return
        
        mensagem_twiml = '<Response><Say language="pt-BR" voice="alice">Radar disparado! Verifique o Telegram!</Say></Response>'
        client.calls.create(twiml=mensagem_twiml, to=destino, from_=TWILIO_NUMERO)
        print(f"📞 [Twilio] Ligacao telefonica efetuada com sucesso para {destino}")
    except Exception as e:
        print(f"❌ Erro Twilio: {e}")

def enviar_alerta_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        # 🔥 CORRIGIDO: "text": mensagem
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"})
        print(f"🔔 [Telegram] Alerta enviado com sucesso para o chat {chat_id}!")
    except Exception as e:
        print(f"❌ Erro Telegram: {e}")

def executar_varredura():
    print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura simulada no Neon...")
    
    if not DATABASE_URL:
        print("🚨 [ERRO LOCAL] Configure a variavel DATABASE_URL no seu terminal!")
        return
        
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT chat_id, origem, destino, preco_alvo, margem, alerta_madrugada, telefone FROM radares")
    radares_usuarios = cursor.fetchall()
    
    print(f"🔎 [Neon] Encontrados {len(radares_usuarios)} radares ativos na nuvem.")
    
    for chat_id, origem, destino, preco_alvo, margem, alerta_madrugada, telefone in radares_usuarios:
        teto_maximo = preco_alvo * (1 + (margem / 100))
        print(f"✈️ Processando: {origem} -> {destino} (Teto cadastrado: R$ {teto_maximo:.2f})")
        
        # Simulador de voo promocional imbatível (R$ 350,00)
        print("⚠️ Ignorando APIs externas... Ativando SIMULADOR de voo ao vivo...")
        voos_simulados = [{"preco": 350.00}]
            
        for voo in voos_simulados:
            preco_real = voo["preco"]
            print(f"   - Valor encontrado pelo simulador: R$ {preco_real:.2f}")
            
            if preco_real <= teto_maximo:
                print(f"🎯 ALVO ENCONTRADO! R$ {preco_real:.2f} é menor que o teto de R$ {teto_maximo:.2f}")
                
                msg = (
                    f"🚨 *RADAR DISPARADO (MOCK TEST)!*\n\n"
                    f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                    f"💵 *Preço Simulado:* R$ {preco_real:.2f}\n"
                    f"🎯 *Seu Limite Máximo:* R$ {teto_maximo:.2f}\n\n"
                    f"⚡ _Parabéns! O fluxo completo do seu código funcionou de ponta a ponta na nuvem!_"
                )
                enviar_alerta_telegram(chat_id, msg)
                
                if alerta_madrugada == "ligacao":
                    disparar_ligacao_twilio(telefone)
                break
        time.sleep(1)
        
    cursor.close()
    conn.close()
    print("🏁 Varredura encerrada.")

if __name__ == "__main__":
    # Executa uma única vez para você ver o estalo no terminal e no celular
    executar_varredura()
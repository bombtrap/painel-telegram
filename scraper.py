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

# Lista de destinos para monitoramento automático (Cidades Isca)
CIDADES_ISCA = ["CWB", "FLN", "POA", "IGU", "EZE", "MVD", "SCL", "NVT"]
DB_NAME = "radares.db"

def disparar_ligacao_twilio():
    """Faz a chamada telefônica via Twilio avisa sobre a passagem na madrugada"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # O Twilio vai ligar para o número configurado no painel da nuvem
        # Se preferir deixar um número fixo, mude para: to="+5511999999999"
        destino_ligacao = os.getenv("TWILIO_NUMERO_DESTINO", TWILIO_NUMERO) 
        
        mensagem_twiml = (
            '<Response>'
            '<Say language="pt-BR" voice="alice">'
            'Atenção! Passagem promocional encontrada na madrugada! Verifique o seu Telegram imediatamente!'
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
    """Envia mensagem de texto formatada para o usuário no Telegram"""
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
    """Consulta a API da Travelpayouts (Aviasales) em busca dos preços mais recentes em cache"""
    url = "https://api.travelpayouts.com/v2/prices/latest"
    
    headers = {
        "X-Access-Token": TRAVELPAYOUTS_TOKEN
    }
    
    params = {
        "origin": origem,       # Corrigido para bater com o argumento da função
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
    """Varre o banco de dados de radares e procura ofertas de passagens"""
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura de preços...")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Garante a existência da tabela caso o bot ainda não tenha rodado
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
    
    # 1. Checa os radares personalizados que os usuários cadastraram
    cursor.execute("SELECT chat_id, origem, destino, preco_maximo FROM radares")
    radares_usuarios = cursor.fetchall()
    
    for chat_id, origem, destino, preco_maximo in radares_usuarios:
        voos = pesquisar_passagens_travelpayouts(origem, destino)
        
        for voo in voos:
            preco_real = voo.get("value")
            if preco_real and preco_real <= preco_maximo:
                msg = (
                    f"🚨 *ALERTA DE PASSAGEM BARATA!*\n\n"
                    f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                    f"💵 *Preço encontrado:* R$ {preco_real:.2f}\n"
                    f"🎯 *Seu limite:* R$ {preco_maximo:.2f}\n"
                    f"📅 *Data de Ida:* {voo.get('depart_date')}\n\n"
                    f"🔗 _Corra para o painel para emitir antes que mude!_"
                )
                enviar_alerta_telegram(chat_id, msg)
                
                # Se encontrar a oferta na calada da noite (00h às 06h), liga para acordar!
                hora_atual = datetime.now().hour
                if 0 <= hora_atual <= 6:
                    disparar_ligacao_twilio()
                break
        time.sleep(1.5)  # Delay leve para respeitar os limites da API
        
    # 2. Checa as Cidades Isca (Varredura geral partindo de SP como Hub padrão)
    origem_hub = "SAO"
    for destino_isca in CIDADES_ISCA:
        voos_isca = pesquisar_passagens_travelpayouts(origem_hub, destino_isca)
        for voo in voos_isca:
            preco_isca = voo.get("value")
            
            # Se uma cidade isca estiver com preço absurdamente baixo (Ex: Menor que R$ 450)
            if preco_isca and preco_isca < 450:
                # Dispara o alerta geral para você (coloque seu Chat ID real do Telegram no painel do Render)
                meu_chat_id = os.getenv("TELEGRAM_CHAT_ID_ADMIN")
                if meu_chat_id:
                    msg_isca = (
                        f"🔥 *PROMOÇÃO ISCA DETECTADA!*\n\n"
                        f"✈️ *Rota:* {origem_hub} ➡️ {destino_isca}\n"
                        f"💵 *Preço bizarro:* R$ {preco_isca:.2f}\n"
                        f"📅 *Data:* {voo.get('depart_date')}"
                    )
                    enviar_alerta_telegram(meu_chat_id, msg_isca)
                    
                    hora_atual = datetime.now().hour
                    if 0 <= hora_atual <= 6:
                        disparar_ligacao_twilio()
                break
        time.sleep(1.5)

    conn.close()
    print("💤 Varredura concluída. Aguardando próximo ciclo...")


if __name__ == "__main__":
    print("🕵️‍♂️ Motor do Scraper Travelpayouts Inicializado com Sucesso!")
    
    # Roda em loop contínuo a cada 30 minutos
    while True:
        try:
            executar_varredura()
        except Exception as e:
            print(f"❌ Erro crítico no loop do scraper: {e}")
        
        time.sleep(1800)  # 1800 segundos = 30 minutos
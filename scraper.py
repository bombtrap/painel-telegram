import os
import time
import psycopg2
import requests
from datetime import datetime, timedelta
from twilio.rest import Client

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
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
        
        mensagem_twiml = '<Response><Say language="pt-BR" voice="alice">Atenção! Radar de passagens disparado! Verifique o seu Telegram imediatamente, o preço alvo foi atingido!</Say></Response>'
        client.calls.create(twiml=mensagem_twiml, to=destino, from_=TWILIO_NUMERO)
        print(f"   📞 [Twilio] Ligação efetuada com sucesso para {destino}")
    except Exception as e:
        print(f"   ❌ Erro Twilio: {e}")

def enviar_alerta_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML", "disable_web_page_preview": True})
        print(f"   🔔 [Telegram] Mensagem entregue ao utilizador com sucesso!")
    except Exception as e:
        print(f"   ❌ Erro Telegram: {e}")

def limpar_preco(preco_bruto):
    try:
        if isinstance(preco_bruto, (int, float)): return float(preco_bruto)
        texto_limpo = str(preco_bruto).replace("R$", "").replace(" ", "")
        if "," in texto_limpo: texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
        elif "." in texto_limpo and len(texto_limpo.split(".")[-1]) == 3: texto_limpo = texto_limpo.replace(".", "")
        return float(texto_limpo)
    except: return None

def consultar_skyscanner(origem, destino, data):
    url = "https://skyscanner-flights4.p.rapidapi.com/api/v1/search"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "skyscanner-flights4.p.rapidapi.com"}
    params = {"origin": origem, "destination": "GRU" if destino == "SAO" else destino, "date": data, "adults": "1", "currency": "BRL", "cabin": "economy", "market": "BR", "locale": "pt-BR", "limit": "15"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200: return res.json().get("results", [])
    except Exception as e: pass
    return []

def formatar_info_flexibilidade(data_atual_obj, data_base_obj):
    diferenca = (data_atual_obj - data_base_obj).days
    if diferenca == 0: return "Na data exata estipulada"
    elif diferenca < 0: return f"{abs(diferenca)} dia(s) ANTES da data estipulada"
    else: return f"{diferenca} dia(s) DEPOIS da data estipulada"

def executar_varredura():
    tokens_gastos_no_ciclo = 0
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # 🚀 NOVO: Adicionado 'ultimo_preco_encontrado' na busca do banco
        cursor.execute("SELECT chat_id, origem, destino, alternativo, max_paradas, skip_principal, paradas_principal, skip_alternativa, data_partida, datas_flexiveis, dias_antes, dias_depois, preco_alvo, margem, alerta_madrugada, telefone, id, ultimo_preco_encontrado FROM radares")
        radares = cursor.fetchall()
    except Exception as e:
        print(f"❌ Erro de ligação ao Neon: {e}")
        return 0

    ISCAS_AUTOMATICAS = ["GIG", "SDU", "CNF", "BSB", "SSA", "FOR"]
    
    print(f"\n========================================================")
    print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] A iniciar varredura em {len(radares)} radar(es) ativo(s)...")
    print(f"========================================================")
    
    # 🚀 NOVO: 'ultimo_preco' adicionado ao desempacotamento
    for chat_id, origem, destino, alternativo, max_paradas, skip_principal, paradas_principal, skip_alternativa, data_partida, datas_flexiveis, dias_antes, dias_depois, preco_alvo, margem, alerta_madrugada, telefone, radar_id, ultimo_preco in radares:
        teto_maximo = float(preco_alvo) * (1 + (float(margem) / 100))
        preco_alvo_float = float(preco_alvo)
        data_base_obj = datetime.strptime(data_partida, "%Y-%m-%d")
        datas_para_pesquisar = []
        
        print(f"\n📡 [RADAR #{radar_id}] Rota: {origem} ➡️️ {destino} | Alvo Tolerância: R$ {teto_maximo:.2f}")

        if datas_flexiveis:
            print(f"   🔄 Flexibilidade Ativa: Analisando do dia -{dias_antes} até +{dias_depois}")
            for i in range(-dias_antes, dias_depois + 1):
                datas_para_pesquisar.append(data_base_obj + timedelta(days=i))
        else:
            datas_para_pesquisar.append(data_base_obj)

        melhor_preco_absoluto = float('inf')
        mensagem_campea = None

        for data_alvo_obj in datas_para_pesquisar:
            data_str = data_alvo_obj.strftime("%Y-%m-%d")
            data_url = data_alvo_obj.strftime("%y%m%d")
            texto_flex = formatar_info_flexibilidade(data_alvo_obj, data_base_obj)

            print(f"\n   📅 Testando data: {data_str} ({texto_flex})")

            # Principal
            tokens_gastos_no_ciclo += 1
            print("      ✈️️ Procurando voos regulares na malha aérea...")
            voos_principais = consultar_skyscanner(origem, destino, data_str)
            if vo
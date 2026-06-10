import os
import time
import sqlite3
import json
import requests
from datetime import datetime
from twilio.rest import Client

# ==================== CONFIGURAÇÕES DE CREDENCIAIS ====================
# Deixe como texto genérico para o GitHub aceitar o upload
AMADEUS_CLIENT_ID = "SEU_AMADEUS_CLIENT_ID_AQUI"
AMADEUS_CLIENT_SECRET = "SEU_AMADEUS_CLIENT_SECRET_AQUI"
TELEGRAM_TOKEN = "SEU_TOKEN_DO_TELEGRAM_AQUI"

# Remova seus códigos reais daqui para proteger sua conta
TWILIO_ACCOUNT_SID = "COLE_SEU_ACCOUNT_SID_AQUI"
TWILIO_AUTH_TOKEN = "COLE_SEU_AUTH_TOKEN_AQUI"
TWILIO_NUMERO = "COLE_SEU_NUMERO_TWILIO_AQUI"

CIDADES_ISCA = ["CWB", "FLN", "POA", "IGU", "EZE", "MVD", "SCL", "NVT"]
# =====================================================================

def obter_token_amadeus():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {"grant_type": "client_credentials", "client_id": AMADEUS_CLIENT_ID, "client_secret": AMADEUS_CLIENT_SECRET}
    try:
        response = requests.post(url, data=data, timeout=15)
        return response.json().get("access_token") if response.status_code == 200 else None
    except Exception:
        return None

def consultar_api_amadeus(token, origem, destino, data):
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"originLocationCode": origem, "destinationLocationCode": destino, "departureDate": data, "adults": 1, "currencyCode": "BRL", "max": 15}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        return response.json().get("data", []) if response.status_code == 200 else []
    except Exception:
        return []

def enviar_mensagem_telegram(chat_id, texto):
    """Envia a mensagem direto para o chat PRIVADO do ID do usuário"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Erro ao notificar chat privado {chat_id}: {e}")

def disparar_ligacao_twilio(numero_destino):
    try:
        if not numero_destino.startswith("+55"):
            numero_limpo = "".join(filter(str.isdigit, numero_destino))
            numero_destino = f"+55{numero_limpo}"
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.calls.create(
            twiml='<Response><Say language="pt-BR" voice="alice">Atenção! Passagem promocional encontrada na madrugada! Verifique o seu Telegram imediatamente!</Say></Response>',
            to=numero_destino, from_=TWILIO_NUMERO
        )
        print(f"📞 Ligação efetuada com sucesso para {numero_destino}!")
    except Exception as e:
        print(f"❌ Erro ao disparar chamada Twilio: {e}")

def validar_janela_horario(hora_voo_str, hora_min_str, hora_max_str):
    try:
        hora_voo = datetime.strptime(hora_voo_str.split("T")[1][:5], "%H:%M").time()
        h_min = datetime.strptime(hora_min_str, "%H:%M").time()
        h_max = datetime.strptime(hora_max_str, "%H:%M").time()
        return h_min <= hora_voo <= h_max
    except Exception:
        return True

def processar_voo(voo, radar, destino_alvo):
    """Filtra e monta a mensagem privada baseada nas preferências do usuário"""
    (user_id, origem, destino_principal, alternativo, max_paradas, 
     skip_na_alternativa, data_partida, hora_min, hora_max, preco_alvo, 
     margem, alerta_madrugada, telefone) = radar
    
    preco = float(voo["price"]["grandTotal"])
    teto_maximo = preco_alvo * (1 + (margem / 100))
    
    if preco > teto_maximo:
        return None

    itinerario = voo["itineraries"][0]
    segments = itinerario["segments"]
    total_paradas_reais = len(segments) - 1
    
    horario_partida_reais = segments[0]["departure"]["at"]
    if not validar_janela_horario(horario_partida_reais, hora_min, hora_max):
        return None

    skiplagging_detectado = False
    aeroporto_desembarque_real = ""
    destino_final_bilhete = segments[-1]["arrival"]["iataCode"]

    if destino_final_bilhete == destino_alvo:
        if total_paradas_reais > max_paradas:
            return None
        aeroporto_desembarque_real = destino_final_bilhete
        tipo_estrategia = "✈️ Voo Direto / Conexão Tradicional"
    else:
        for segment in segments[:-1]:
            if segment["arrival"]["iataCode"] == destino_alvo:
                skiplagging_detectado = True
                aeroporto_desembarque_real = destino_alvo
                break
        if not skiplagging_detectado:
            return None
        tipo_estrategia = "🚨 OPORTUNIDADE SKIPLAGGING (Desembarque Oculto)"

    tag_preco = "🔥 PECHINCHA TOTAL (Abaixo do Teto)" if preco <= preco_alvo else "⚠️ DENTRO DA MARGEM DE TOLERÂNCIA"
    lista_rota = [seg["departure"]["iataCode"] for seg in segments] + [destino_final_bilhete]
    rota_visual = " ➡️ ".join(lista_rota)
    
    link_compra = f"https://www.google.com/travel/flights?q=Flights%20to%20{destino_final_bilhete}%20from%20{origem}%20on%20{data_partida}%20one%20way"

    logistica = f"📍 Você descerá em: *{aeroporto_desembarque_real}*"
    if aeroporto_desembarque_real in ["GIG", "SDU"]:
        logistica += "\n🚌 *Nota Logística:* Desembarque no RJ + pegue o ônibus para SP (8h de viagem)."

    mensagem = (
        f"{tag_preco}\n"
        f"*{tipo_estrategia}*\n\n"
        f"🗺️ *Rota Completa do Bilhete:* `{rota_visual}`\n"
        f"💵 *Preço Total:* R$ {preco:.2f}\n"
        f"📅 *Partida:* {horario_partida_reais.split('T')[0]} às {horario_partida_reais.split('T')[1][:5]}\n\n"
        f"{logistica}\n\n"
        f"🔗 [Clique aqui para abrir no Google Flights e Comprar]({link_compra})\n\n"
        f"⚠️ _Se for Skiplagging, viaje APENAS com mala de mão e abandone os trechos finais!_"
    )
    
    return {"mensagem": message, "preco": preco, "alerta_madrugada": alerta_madrugada, "telefone": telefone, "user_id": user_id}

def executar_scraps_ativos():
    print(f"[{datetime.now()}] 🔄 Lendo radares ativos no banco de dados...")
    token = obter_token_amadeus()
    if not token: return

    conn = sqlite3.connect("radares.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, origem, destino, alternativo, max_paradas, skip_alternativa, data_partida, hora_min, hora_max, preco_alvo, margem, alerta_madrugada, telefone FROM radares")
        radares = cursor.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return
    conn.close()

    for radar in radares:
        # Unpacking explícito e seguro por nome de variável
        (user_id, origem, destino_principal, destino_alternativo, max_paradas, 
         skip_na_alternativa, data_voo, hora_min, hora_max, preco_alvo, 
         margem, alerta_madrugada, telefone) = radar

        alertas_disparados = []

        # --- BUSCA ROTA PRINCIPAL ---
        voos_diretos = consultar_api_amadeus(token, origem, destino_principal, data_voo)
        for v in voos_diretos:
            res = processar_voo(v, radar, destino_principal)
            if res: alertas_disparados.append(res)

        for isca in CIDADES_ISCA:
            if isca == destino_principal: continue
            voos_iscas = consultar_api_amadeus(token, origem, isca, data_voo)
            for v in voos_iscas:
                res = processar_voo(v, radar, destino_principal)
                if res: alertas_disparados.append(res)

        # --- BUSCA ROTA ALTERNATIVA ---
        if destino_alternativo:
            voos_alt = consultar_api_amadeus(token, origem, destino_alternativo, data_voo)
            for v in voos_alt:
                res = processar_voo(v, radar, destino_alternativo)
                if res: alertas_disparados.append(res)
                
            if skip_na_alternativa == "sim":
                for isca in CIDADES_ISCA:
                    if isca == destino_alternativo: continue
                    voos_iscas_alt = consultar_api_amadeus(token, origem, isca, data_voo)
                    for v in voos_iscas_alt:
                        res = processar_voo(v, radar, destino_alternativo)
                        if res: alertas_disparados.append(res)

        # --- DISPARO PRIVADO DOS ALERTAS ---
        if alertas_disparados:
            alertas_disparados.sort(key=lambda x: x["preco"])
            melhor_oferta = alertas_disparados[0]
            
            # Envia a mensagem EXCLUSIVAMENTE para o chat privado do user_id dono desse radar
            enviar_mensagem_telegram(melhor_oferta["user_id"], melhor_oferta["mensagem"])
            
            # Disparador do telefone na madrugada (Corrigido para hora_atual)
            hora_atual = datetime.now().hour
            if 1 <= hora_atual <= 5:
                if melhor_oferta["alerta_madrugada"] == "ligacao" and melhor_oferta["telefone"]:
                    disparar_ligacao_twilio(melhor_oferta["telefone"])

if __name__ == "__main__":
    print("🚀 Scraper ativo e calibrado para as 03:00 e 14:00...")
    ja_rodou_madrugada = False
    ja_rodou_tarde = False

    while True:
        hora_atual = datetime.now().hour
        if hora_atual == 3:
            if not ja_rodou_madrugada:
                executar_scraps_ativos()
                ja_rodou_madrugada = True
                ja_rodou_tarde = False
        elif hora_atual == 14:
            if not ja_rodou_tarde:
                executar_scraps_ativos()
                ja_rodou_tarde = True
                ja_rodou_madrugada = False
        else:
            ja_rodou_madrugada = False
            ja_rodou_tarde = False

        time.sleep(60)
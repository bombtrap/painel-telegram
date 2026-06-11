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
        print(f"📞 [Twilio] Ligação efetuada para {destino}")
    except Exception as e:
        print(f"❌ Erro Twilio: {e}")

def enviar_alerta_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown", "disable_web_page_preview": True})
        print(f"🔔 [Telegram] Alerta disparado para {chat_id}!")
    except Exception as e:
        print(f"Erro Telegram: {e}")

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
        cursor.execute("SELECT chat_id, origem, destino, alternativo, max_paradas, skip_principal, paradas_principal, skip_alternativa, data_partida, datas_flexiveis, dias_antes, dias_depois, preco_alvo, margem, alerta_madrugada, telefone, id FROM radares")
        radares = cursor.fetchall()
    except Exception as e:
        print(f"Erro no Neon: {e}")
        return 0

    ISCAS_AUTOMATICAS = ["GIG", "SDU", "CNF", "BSB", "SSA", "FOR"]
    
    for chat_id, origem, destino, alternativo, max_paradas, skip_principal, paradas_principal, skip_alternativa, data_partida, datas_flexiveis, dias_antes, dias_depois, preco_alvo, margem, alerta_madrugada, telefone, radar_id in radares:
        teto_maximo = preco_alvo * (1 + (margem / 100))
        data_base_obj = datetime.strptime(data_partida, "%Y-%m-%d")
        datas_para_pesquisar = []
        
        if datas_flexiveis:
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

            # Principal
            tokens_gastos_no_ciclo += 1
            voos_principais = consultar_skyscanner(origem, destino, data_str)
            if voos_principais:
                voos_principais.sort(key=lambda x: limpar_preco(x.get("price_raw")) or 999999)
                for voo in voos_principais:
                    preco_reg = limpar_preco(voo.get("price_raw"))
                    if not preco_reg or (paradas_principal == 0 and "direct" not in voo.get("tags", [])): continue
                    if preco_reg <= teto_maximo and preco_reg < melhor_preco_absoluto:
                        melhor_preco_absoluto = preco_reg
                        dest_url = "gru" if destino == "SAO" else destino.lower()
                        link = f"https://www.skyscanner.com.br/transporte/voos/{origem.lower()}/{dest_url}/{data_url}/?adults=1&cabinclass=economy&locale=pt-BR&market=BR&currency=BRL"
                        mensagem_campea = f"🏆 *MELHOR OFERTA ENCONTRADA (Voo Regular)!*\n\n✈️ *Rota:* {origem} ➡️ {destino}\n📅 *Data:* {data_str}\n💵 *Preço Real:* R$ {preco_reg:.2f}\n🔄 _{texto_flex}_\n\n🔗 *[🛒 COMPRAR NO SKYSCANNER]({link})*"
                    break 

            # Skiplagging Principal
            if skip_principal == "sim" and paradas_principal >= 1:
                destinos_teste = [iscal for iscal in ISCAS_AUTOMATICAS if iscal != destino and iscal != origem]
                for isca in destinos_teste:
                    tokens_gastos_no_ciclo += 1
                    voos_isca = consultar_skyscanner(origem, isca, data_str)
                    if not voos_isca: continue
                    voos_isca.sort(key=lambda x: limpar_preco(x.get("price_raw")) or 999999)
                    for voo_i in voos_isca:
                        preco_i = limpar_preco(voo_i.get("price_raw"))
                        if not preco_i or preco_i > teto_maximo: continue
                        if destino in str(voo_i.get("legs", "")).upper() or (destino == "SAO" and any(ap in str(voo_i.get("legs", "")).upper() for ap in ["GRU", "CGH", "VCP"])):
                            if preco_i < melhor_preco_absoluto:
                                melhor_preco_absoluto = preco_i
                                link = f"https://www.skyscanner.com.br/transporte/voos/{origem.lower()}/{isca.lower()}/{data_url}/?adults=1&cabinclass=economy&locale=pt-BR&market=BR&currency=BRL"
                                mensagem_campea = f"🏆🔥 *MELHOR OFERTA - PASSAGEM OCULTA (SKIPLAGGING)!*\n\n✈️ *Voo:* {origem} ➡️ {isca} (Abandone em {destino})\n📅 *Data:* {data_str}\n💵 *Preço Real:* R$ {preco_i:.2f}\n🔄 _{texto_flex}_\n\n🔗 *[🛒 COMPRAR NO SKYSCANNER]({link})*\n⚠️ Leve apenas bagagem de mão!"
                            break 
                    if melhor_preco_absoluto <= preco_i: break 

            # Alternativo
            if alternativo:
                tokens_gastos_no_ciclo += 1
                voos_alternativos = consultar_skyscanner(origem, alternativo, data_str)
                if voos_alternativos:
                    voos_alternativos.sort(key=lambda x: limpar_preco(x.get("price_raw")) or 999999)
                    for voo_alt in voos_alternativos:
                        preco_alt = limpar_preco(voo_alt.get("price_raw"))
                        if not preco_alt or preco_alt > teto_maximo: continue
                        if max_paradas == 0 and "direct" not in voo_alt.get("tags", []): continue
                        contem_destino = destino in str(voo_alt.get("legs", "")).upper() or (destino == "SAO" and any(ap in str(voo_alt.get("legs", "")).upper() for ap in ["GRU", "CGH", "VCP"]))
                        if preco_alt < melhor_preco_absoluto:
                            melhor_preco_absoluto = preco_alt
                            link = f"https://www.skyscanner.com.br/transporte/voos/{origem.lower()}/{alternativo.lower()}/{data_url}/?adults=1&cabinclass=economy&locale=pt-BR&market=BR&currency=BRL"
                            if skip_alternativa == "sim" and contem_destino and max_paradas >= 1:
                                mensagem_campea = f"🏆🔥 *MELHOR OFERTA - SKIP NA ALTERNATIVA!*\n\n✈️ *Voo:* {origem} ➡️ {alternativo} (Desça em {destino})\n📅 *Data:* {data_str}\n💵 *Preço:* R$ {preco_alt:.2f}\n🔄 _{texto_flex}_\n\n🔗 *[🛒 COMPRAR NO SKYSCANNER]({link})*"
                            elif skip_alternativa == "nao" or not contem_destino:
                                mensagem_campea = f"🏆🚌 *MELHOR OFERTA - ALTERNATIVA REGULAR!*\n\n✈️ *Voo:* {origem} ➡️ {alternativo} (Termine via terra até {destino})\n📅 *Data:* {data_str}\n💵 *Preço:* R$ {preco_alt:.2f}\n🔄 _{texto_flex}_\n\n🔗 *[🛒 COMPRAR NO SKYSCANNER]({link})*"
                        break

            time.sleep(1.5) 

        if mensagem_campea:
            enviar_alerta_telegram(chat_id, mensagem_campea)
            if alerta_madrugada == "ligacao" and telefone:
                disparar_ligacao_twilio(telefone)

    cursor.close()
    conn.close()
    return tokens_gastos_no_ciclo

if __name__ == "__main__":
    TOKENS_MENSAIS = 10000
    DIAS_MES = 30
    MARGEM_SEGURANCA = 0.95 
    TOKENS_POR_DIA = (TOKENS_MENSAIS / DIAS_MES) * MARGEM_SEGURANCA
    
    while True:
        reqs_do_ciclo = executar_varredura()
        if reqs_do_ciclo == 0:
            time.sleep(3600)
            continue
            
        tempo_espera = (86400 * reqs_do_ciclo) / TOKENS_POR_DIA
        if tempo_espera < 900: tempo_espera = 900
        time.sleep(tempo_espera)
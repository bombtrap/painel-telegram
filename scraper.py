import os
import time
import psycopg2
import requests
from datetime import datetime
from twilio.rest import Client

# Credenciais do sistema
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "e271a38ef1msh38a3459232ba8f8p16efccjsn4a430399bb45")
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
    try:
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown", "disable_web_page_preview": False})
        print(f"🔔 [Telegram] Alerta enviado com sucesso para o chat {chat_id}!")
    except Exception as e:
        print(f"❌ Erro Telegram: {e}")

def pesquisar_passagens_skyscanner(origem, destino, data_partida):
    """Busca voos em tempo real tratando a chave price_raw e limpando formatacao de moeda"""
    url = "https://skyscanner-flights4.p.rapidapi.com/api/v1/search"
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "skyscanner-flights4.p.rapidapi.com"
    }
    
    params = {
        "origin": origem,
        "destination": "GRU" if destino == "SAO" else destino,
        "date": data_partida, 
        "adults": "1",
        "currency": "BRL",
        "cabin": "economy",
        "market": "BR",
        "locale": "pt-BR",
        "limit": "20"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            dados = response.json()
            
            total_encontrado = dados.get("results_count", 0)
            lista_voos = []
            voos = dados.get("results", [])
            
            if total_encontrado > 0 and voos:
                for item in voos:
                    preco_bruto = item.get("price_raw") or item.get("price")
                    
                    if preco_bruto is not None:
                        try:
                            if isinstance(preco_bruto, (int, float)):
                                preco_real = float(preco_bruto)
                            else:
                                texto_limpo = str(preco_bruto).replace("R$", "").replace(" ", "")
                                if "," in texto_limpo:
                                    texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
                                elif "." in texto_limpo and len(texto_limpo.split(".")[-1]) == 3:
                                    texto_limpo = texto_limpo.replace(".", "")
                                
                                preco_real = float(texto_limpo)
                                
                            lista_voos.append({"preco": preco_real})
                        except:
                            continue
                return lista_voos
        else:
            print(f"⚠️ API retornou Status {response.status_code}.")
    except Exception as e:
        print(f"⚠️ Falha de conexao com o Skyscanner: {e}")
    return []

def executar_varredura():
    print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura no Neon...")
    
    if not DATABASE_URL:
        print("🚨 [ERRO LOCAL] Variavel DATABASE_URL ausente no terminal!")
        return
        
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT chat_id, origem, destino, data_partida, preco_alvo, margem, alerta_madrugada, telefone FROM radares")
    radares_usuarios = cursor.fetchall()
    
    print(f"🔎 [Neon] Encontrados {len(radares_usuarios)} radares ativos na nuvem.")
    
    for chat_id, origem, destino, data_partida, preco_alvo, margem, alerta_madrugada, telefone in radares_usuarios:
        teto_maximo = preco_alvo * (1 + (margem / 100))
        print(f"✈️ Processando: {origem} -> {destino} para o dia {data_partida} (Teto: R$ {teto_maximo:.2f})")
        
        voos = pesquisar_passagens_skyscanner(origem, destino, data_partida)
        
        if not voos:
            print("ℹ️ Nenhum voo retornado ou processado para este alvo agora.")
            continue
            
        print(f"   📊 Processadas {len(voos)} tarifas reais com sucesso.")
        
        voos.sort(key=lambda x: x["preco"])
        menor_preco = voos[0]["preco"]
        print(f"   - Menor tarifa real encontrada: R$ {menor_preco:.2f}")
        
        if menor_preco <= teto_maximo:
            print(f"🎯 ALVO REAL ENCONTRADO! R$ {menor_preco:.2f} <= R$ {teto_maximo:.2f}")
            
            # 🔥 GERADOR DE LINK DINÂMICO DO SKYSCANNER
            # Converte '2026-06-10' para '260610' (Formato de URL do Skyscanner)
            data_url = data_partida.replace("-", "")[2:]
            destino_url = "gru" if destino == "SAO" else destino.lower()
            
            link_skyscanner = f"https://www.skyscanner.com.br/transporte/voos/{origem.lower()}/{destino_url}/{data_url}/?adults=1&cabinclass=economy&locale=pt-BR&market=BR&currency=BRL"
            
            msg = (
                f"🚨 *RADAR DISPARADO (OFERTA REAL)!*\n\n"
                f"✈️ *Rota:* {origem} ➡️ {destino}\n"
                f"📅 *Data do Voo:* {data_partida}\n"
                f"💵 *Preço Encontrado:* R$ {menor_preco:.2f}\n"
                f"🎯 *Seu Limite Máximo:* R$ {teto_maximo:.2f}\n\n"
                f"🔗 *[🛒 CLIQUE AQUI PARA COMPRAR NO SKYSCANNER]({link_skyscanner})*\n\n"
                f"⚡ _Aproveite a oportunidade antes que a tarifa mude!_"
            )
            enviar_alerta_telegram(chat_id, msg)
            
            if alerta_madrugada == "ligacao":
                disparar_ligacao_twilio(telefone)
        else:
            print(f"   ❌ Preco mais baixo (R$ {menor_preco:.2f}) ainda acima do teto (R$ {teto_maximo:.2f}).")
        time.sleep(2)
        
    cursor.close()
    conn.close()
    print("🏁 Varredura encerrada.")

if __name__ == "__main__":
    executar_varredura()
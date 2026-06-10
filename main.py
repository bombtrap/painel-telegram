import sys

# =====================================================================
# 🔥 CAIXA-PRETA: Captura erros de falta de biblioteca antes do app cair
# =====================================================================
try:
    import subprocess
    import os
    import threading
    import time
    import json
    import psycopg2
    import requests
    from http.server import BaseHTTPRequestHandler, HTTPServer
except Exception as e:
    print(f"\n🚨 [ERRO CRÍTICO DE INICIALIZAÇÃO] O Python nao conseguiu iniciar o main.py: {e}\n")
    sys.exit(1)


class RenderHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(b"Rastreador de Voos Ativo e Operando 24h!")
        
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Recebe os dados completos do painel do Telegram e grava no Neon"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            db_url = os.getenv("DATABASE_URL")
            telegram_token = os.getenv("TELEGRAM_TOKEN")
            
            if not db_url:
                print("🚨 [ERRO] DATABASE_URL vazia no recebimento do POST!")
                self.send_response(500)
                self._set_cors_headers()
                self.end_headers()
                return

            dados = json.loads(post_data.decode('utf-8'))
            chat_id = dados.get("chat_id")
            origem = dados.get("origem")
            destino = dados.get("destino")
            alternativo = dados.get("alternativo", "")
            max_paradas = int(dados.get("maxParadas", 2))
            skip_alternativa = dados.get("skipAlternativa", "nao")
            data_partida = dados.get("dataPartida")
            hora_min = dados.get("horaMin", "00:00")
            hora_max = dados.get("horaMax", "23:59")
            preco_alvo = float(dados.get("precoAlvo", 0))
            margem = int(dados.get("margem", 0))
            alerta_madrugada = dados.get("alertaMadrugada", "telegram")
            telefone = dados.get("telefone", "")
            
            if chat_id and origem and destino and preco_alvo:
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor()
                
                # Insere o radar com a estrutura completa
                cursor.execute('''
                    INSERT INTO radares (
                        chat_id, origem, destino, alternativo, max_paradas, 
                        skip_alternativa, data_partida, hora_min, hora_max, 
                        preco_alvo, margem, alerta_madrugada, telefone
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    str(chat_id), str(origem).upper(), str(destino).upper(), str(alternativo).upper(),
                    max_paradas, str(skip_alternativa), str(data_partida), str(hora_min), str(hora_max),
                    preco_alvo, margem, str(alerta_madrugada), str(telefone)
                ))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                print(f"✅ [API] Radar Premium Gravado com Sucesso para o Chat {chat_id}")
                
                # Montagem do Alerta Visual de Confirmacao
                preco_maximo_alerta = preco_alvo * (1 + (margem / 100))
                
                if alerta_madrugada == "telegram":
                    estrategia_txt = "💬 Apenas mensagem de texto no Telegram"
                elif alerta_madrugada == "ligacao":
                    estrategia_txt = f"📞 Ligação Telefônica Real no número ({telefone})"
                else:
                    estrategia_txt = "📢 Alerta de Sirene via aplicativo Pushover"
                    
                link_flights = f"https://www.google.com/travel/flights?q=Flights%20to%20{destino}%20from%20{origem}%20on%20{data_partida}"
                
                msg_telegram = (
                    f"✅ *Radar Configurado com Sucesso!*\n\n"
                    f"1🛫 *Origem:* {origem.upper()}\n"
                    f"🛬 *Destino Principal:* {destino.upper()}\n"
                )
                if alternativo:
                    msg_telegram += f"🔄 *Destino Alternativo:* {alternativo.upper()}\n"
                    
                msg_telegram += (
                    f"💵 *Preço Alvo:* R$ {preco_alvo:.2f} (Alerta máximo até: R$ {preco_maximo_alerta:.2f})\n"
                    f"📅 *Data:* {data_partida}\n\n"
                    f"🔔 *Estratégia de Madrugada:* \n"
                    f"{estrategia_txt}\n\n"
                    f"🔗 [Acompanhar voo manualmente no Google Flights]({link_flights})\n\n"
                    f"_Rastreamento privado ativado de forma exclusiva para você!_"
                )
                
                # Dispara a mensagem para o chat do Telegram do usuario
                url_tg_api = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                requests.post(url_tg_api, json={
                    "chat_id": chat_id,
                    "text": msg_telegram,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                })
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            else:
                self.send_response(400)
                self._set_cors_headers()
                self.end_headers()
                
        except Exception as e:
            print(f"❌ Erro ao processar o salvamento do radar: {e}")
            self.send_response(500)
            self._set_cors_headers()
            self.end_headers()


def inicializar_banco_de_dados():
    """Garante a sincronizacao da tabela estruturada antes dos scripts rodarem"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("🚨 [ERRO] Nao foi possivel sincronizar o banco: DATABASE_URL ausente.")
        return

    print("🗄️ Sincronizando tabelas com a Nuvem (Neon)...")
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Remove a tabela antiga se houver descompasso de colunas dos testes simples
        cursor.execute("DROP TABLE IF EXISTS radares CASCADE;")
        
        # Cria a tabela definitiva com as colunas completas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS radares (
                id SERIAL PRIMARY KEY,
                chat_id TEXT,
                origem TEXT,
                destino TEXT,
                alternativo TEXT,
                max_paradas INTEGER,
                skip_alternativa TEXT,
                data_partida TEXT,
                hora_min TEXT,
                hora_max TEXT,
                preco_alvo DOUBLE PRECISION,
                margem INTEGER,
                alerta_madrugada TEXT,
                telefone TEXT
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        print("🟩 Banco de dados estruturado e pronto para uso!")
    except Exception as e:
        print(f"❌ Erro na sincronizacao inicial do banco: {e}")


def ligar_servidor_http():
    porta = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", porta), RenderHandler)
    print(f"🌍 Servidor API do Render ativo na porta {porta}")
    server.serve_forever()

def loop_auto_ping():
    url_publica = os.environ.get("RENDER_EXTERNAL_URL")
    if not url_publica:
        return
    time.sleep(180)
    while True:
        try: requests.get(url_publica)
        except: pass
        time.sleep(720)


if __name__ == "__main__":
    print("🚀 Iniciando o ecossistema com API PostgreSQL externa...")
    
    # 1. Ajusta o banco de dados primeiro de tudo!
    inicializar_banco_de_dados()
    
    # 2. Liga as portas de rede da API
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    
    # 3. Dispara os motores filhos sabendo que a tabela ja existe perfeitamente
    processo_bot = subprocess.Popen([sys.executable, "-u", "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "-u", "scraper.py"])
    
    processo_bot.wait()
    processo_scraper.wait()
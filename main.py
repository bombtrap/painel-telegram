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
        """Adiciona as permissões de segurança para o GitHub Pages conseguir conversar com o Render"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Responde à checagem de segurança inicial do navegador (Preflight)"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Pings normais de navegador para checar se o app está de pé"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(b"Rastreador de Voos Ativo e Operando 24h!")
        
    def do_HEAD(self):
        """Pings automáticos do UptimeRobot e do próprio Render"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Recebe os dados do painel do Telegram e grava no PostgreSQL do Neon"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Resgata a variável de conexão em nuvem
            db_url = os.getenv("DATABASE_URL")
            
            if not db_url:
                print("🚨 [ERRO CRÍTICO] A variavel DATABASE_URL esta completamente VAZIA no Render!")
                self.send_response(500)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"Erro: DATABASE_URL nao configurada no Render.")
                return

            # Decodifica os dados recebidos do formulário
            dados = json.loads(post_data.decode('utf-8'))
            chat_id = dados.get("chat_id")
            origem = dados.get("origem")
            destino = dados.get("destino")
            preco_maximo = dados.get("preco_maximo")
            
            # Validação dos dados obrigatórios
            if chat_id and origem and destino and preco_maximo:
                # Conecta ao banco Neon em nuvem
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor()
                
                # Garante que a tabela existe no Postgres
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS radares (
                        id SERIAL PRIMARY KEY,
                        chat_id TEXT,
                        origem TEXT,
                        destino TEXT,
                        preco_maximo DOUBLE PRECISION
                    )
                ''')
                
                # Insere o novo radar usando a sintaxe %s do PostgreSQL
                cursor.execute(
                    "INSERT INTO radares (chat_id, origem, destino, preco_maximo) VALUES (%s, %s, %s, %s)",
                    (str(chat_id), str(origem).upper(), str(destino).upper(), float(preco_maximo))
                )
                
                conn.commit()
                cursor.close()
                conn.close()
                
                print(f"✅ [API] Novo radar gravado no Neon: {origem.upper()} -> {destino.upper()} (Chat: {chat_id})")
                
                # Devolve uma resposta de sucesso para o painel
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                resposta = {"success": True, "message": "Radar cadastrado com sucesso!"}
                self.wfile.write(json.dumps(resposta).encode('utf-8'))
            else:
                print("⚠️ [API] Dados recebidos incompletos ou mal formatados.")
                self.send_response(400)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"Dados incompletos")
                
        except Exception as e:
            print(f"❌ Erro ao processar o salvamento do radar: {e}")
            self.send_response(500)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))


def ligar_servidor_http():
    """Inicializa o servidor HTTP da API na porta correta estipulada pelo Render"""
    porta = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", porta), RenderHandler)
    print(f"🌍 Servidor API do Render ativo na porta {porta}")
    server.serve_forever()

def loop_auto_ping():
    """Evita o modo 'sono' do plano gratuito fazendo pings internos no próprio app"""
    url_publica = os.environ.get("RENDER_EXTERNAL_URL")
    if not url_publica:
        return
    time.sleep(180)
    while True:
        try:
            requests.get(url_publica)
        except:
            pass
        time.sleep(720)


if __name__ == "__main__":
    print("🚀 Iniciando o ecossistema com API PostgreSQL externa...")
    
    # Inicia o servidor HTTP e o Anti-Sono em threads paralelas
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    
    # Dispara o bot e o scraper usando o parâmetro "-u" para desativar o cache de logs
    processo_bot = subprocess.Popen([sys.executable, "-u", "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "-u", "scraper.py"])
    
    # Mantém o main.py rodando enquanto os scripts filhos estiverem vivos
    processo_bot.wait()
    processo_scraper.wait()
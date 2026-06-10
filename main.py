import subprocess
import sys
import os
import threading
import time
import json
import psycopg2 # Mudamos para psycopg2
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

DATABASE_URL = os.getenv("DATABASE_URL")

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
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            dados = json.loads(post_data.decode('utf-8'))
            chat_id = dados.get("chat_id")
            origem = dados.get("origem")
            destino = dados.get("destino")
            preco_maximo = dados.get("preco_maximo")
            
            if chat_id and origem and destino and preco_maximo:
                # Conecta no PostgreSQL do Neon
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
                # No Postgres usamos %s no lugar de ?
                cursor.execute(
                    "INSERT INTO radares (chat_id, origem, destino, preco_maximo) VALUES (%s, %s, %s, %s)",
                    (str(chat_id), str(origem).upper(), str(destino).upper(), float(preco_maximo))
                )
                conn.commit()
                cursor.close()
                conn.close()
                
                print(f"✅ [API] Novo radar gravado no Neon: {origem} -> {destino}")
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                resposta = {"success": True, "message": "Radar cadastrado com sucesso!"}
                self.wfile.write(json.dumps(resposta).encode('utf-8'))
            else:
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
        try:
            requests.get(url_publica)
        except:
            pass
        time.sleep(720)

if __name__ == "__main__":
    print("🚀 Iniciando o ecossistema com API PostgreSQL externa...")
    
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    
    processo_bot = subprocess.Popen([sys.executable, "-u", "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "-u", "scraper.py"])
    
    processo_bot.wait()
    processo_scraper.wait()
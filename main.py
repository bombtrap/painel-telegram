import subprocess
import sys
import os
import threading
import time
import json
import sqlite3
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_NAME = "radares.db"

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
        """Pings normais de navegador"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(b"Rastreador de Voos Ativo e Operando 24h!")
        
    def do_HEAD(self):
        """Pings do UptimeRobot"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Recebe os dados do formulário do Telegram e grava no SQLite"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Transforma o texto recebido em um dicionário Python
            dados = json.loads(post_data.decode('utf-8'))
            chat_id = dados.get("chat_id")
            origem = dados.get("origem")
            destino = dados.get("destino")
            preco_maximo = dados.get("preco_maximo")
            
            if chat_id and origem and destino and preco_maximo:
                # Conecta e grava direto no banco SQLite dentro do Render
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS radares (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        origem TEXT,
                        destino TEXT,
                        preco_maximo REAL
                    )
                ''')
                cursor.execute(
                    "INSERT INTO radares (chat_id, origem, destino, preco_maximo) VALUES (?, ?, ?, ?)",
                    (str(chat_id), str(origem).upper(), str(destino).upper(), float(preco_maximo))
                )
                conn.commit()
                conn.close()
                
                print(f"✅ [API] Novo radar gravado: {origem} -> {destino} (Chat: {chat_id})")
                
                # Responde de volta para o formulário dizendo que deu certo
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
    print("🚀 Iniciando o ecossistema com API e Protecao Anti-Sono...")
    
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    
    processo_bot = subprocess.Popen([sys.executable, "-u", "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "-u", "scraper.py"])
    
    processo_bot.wait()
    processo_scraper.wait()
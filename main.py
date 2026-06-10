import subprocess
import sys
import os
import threading
import time
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# Servidor fantasma atualizado para aceitar requisições GET e HEAD
class RenderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Rastreador de Voos Ativo e Operando 24h!")
        
    def do_HEAD(self):
        # Respondendo com sucesso 200 para os pings do UptimeRobot
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def ligar_servidor_http():
    porta = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", porta), RenderHandler)
    print(f"🌍 Servidor de checagem do Render ativo na porta {porta}")
    server.serve_forever()

def loop_auto_ping():
    """Faz um ping na própria URL a cada 12 minutos para impedir o Render de dormir"""
    url_publica = os.environ.get("RENDER_EXTERNAL_URL")
    
    if not url_publica:
        print("⚠️ RENDER_EXTERNAL_URL nao encontrada (ambiente local). Auto-ping desativado.")
        return
        
    print(f"📶 Sistema de Auto-Ping inicializado para: {url_publica}")
    time.sleep(180)
    
    while True:
        try:
            response = requests.get(url_publica)
            print(f"🔄 [Auto-Ping] Ping enviado com sucesso! Status do servidor: {response.status_code}")
        except Exception as e:
            print(f"⚠️ [Auto-Ping] Falha ao tentar pingar o servidor: {e}")
        
        time.sleep(720)

if __name__ == "__main__":
    print("🚀 Iniciando o ecossistema com proteção anti-sono...")
    
    # 1. Liga o servidor HTTP que o Render exige
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    
    # 2. Liga o robô interno de Auto-Ping
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    
    # 3. Dispara o bot e o scraper em paralelo
    processo_bot = subprocess.Popen([sys.executable, "-u", "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "-u", "scraper.py"])
    
    processo_bot.wait()
    processo_scraper.wait()
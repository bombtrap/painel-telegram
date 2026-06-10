import subprocess
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Servidor fantasma apenas para o Render não dar erro de Porta (Port Timeout)
class RenderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Rastreador de Voos Ativo e Operando 24h!")

def ligar_servidor_http():
    # O Render injeta automaticamente a porta necessária na variável PORT
    porta = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", porta), RenderHandler)
    print(f"🌍 Servidor de checagem do Render ativo na porta {porta}")
    server.serve_forever()

if __name__ == "__main__":
    print("🚀 Iniciando o ecossistema: Bot + Scraper...")
    
    # Liga o servidor HTTP em uma linha paralela (Thread)
    threading.Thread(target=ligar_servidor_http, daemon=True).start()
    
    # Dispara o bot e o scraper em paralelo
    processo_bot = subprocess.Popen([sys.executable, "bot.py"])
    processo_scraper = subprocess.Popen([sys.executable, "scraper.py"])
    
    # Mantém o script principal vivo guardando os robôs
    processo_bot.wait()
    processo_scraper.wait()
import os
import sys
import subprocess
import threading
import time
import psycopg2
import psycopg2.extras
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
DATABASE_URL = os.getenv("DATABASE_URL")

def iniciar_banco():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS radares (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(50),
                origem VARCHAR(10),
                destino VARCHAR(10),
                alternativo VARCHAR(10),
                max_paradas INT,
                skip_principal VARCHAR(5),
                paradas_principal INT,
                skip_alternativa VARCHAR(5),
                data_partida DATE,
                datas_flexiveis BOOLEAN,
                dias_antes INT,
                dias_depois INT,
                preco_alvo NUMERIC,
                margem NUMERIC
            )
        """)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='radares' AND column_name='alerta_madrugada'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE radares ADD COLUMN alerta_madrugada VARCHAR(20) DEFAULT 'telegram', ADD COLUMN telefone VARCHAR(20)")
        conn.commit()
        cursor.close()
        conn.close()
        print("🗄️ Tabela 'radares' verificada/atualizada no Neon!")
    except Exception as e:
        print(f"❌ Erro ao iniciar base de dados: {e}")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/radar/<int:radar_id>', methods=['GET'])
def get_radar(radar_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM radares WHERE id = %s", (radar_id,))
        radar = cursor.fetchone()
        cursor.close()
        conn.close()
        if radar:
            if radar.get('data_partida'):
                try:
                    radar['data_partida'] = radar['data_partida'].strftime('%Y-%m-%d')
                except AttributeError:
                    pass
            return jsonify(radar), 200
        return jsonify({"erro": "Radar não encontrado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/salvar', methods=['POST'])
def salvar_radar():
    dados = request.json
    radar_id = dados.get('id')
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        if radar_id:
            cursor.execute("""
                UPDATE radares SET 
                    origem = %s, destino = %s, alternativo = %s, max_paradas = %s, 
                    skip_principal = %s, paradas_principal = %s, skip_alternativa = %s, 
                    data_partida = %s, datas_flexiveis = %s, dias_antes = %s, 
                    dias_depois = %s, preco_alvo = %s, margem = %s,
                    alerta_madrugada = %s, telefone = %s
                WHERE id = %s
            """, (
                dados['origem'], dados['destino'], dados.get('alternativo', ''), dados['max_paradas'],
                dados['skip_principal'], dados['paradas_principal'], dados['skip_alternativa'],
                dados['data_partida'], dados['datas_flexiveis'], dados['dias_antes'],
                dados['dias_depois'], dados['preco_alvo'], dados['margem'], 
                dados['alerta_madrugada'], dados['telefone'], radar_id
            ))
        else:
            cursor.execute("""
                INSERT INTO radares (
                    chat_id, origem, destino, alternativo, max_paradas, 
                    skip_principal, paradas_principal, skip_alternativa, 
                    data_partida, datas_flexiveis, dias_antes, dias_depois, 
                    preco_alvo, margem, alerta_madrugada, telefone
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                dados['chat_id'], dados['origem'], dados['destino'], dados.get('alternativo', ''), 
                dados['max_paradas'], dados['skip_principal'], dados['paradas_principal'], 
                dados['skip_alternativa'], dados['data_partida'], dados['datas_flexiveis'], 
                dados['dias_antes'], dados['dias_depois'], dados['preco_alvo'], dados['margem'],
                dados['alerta_madrugada'], dados['telefone']
            ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

def loop_auto_ping():
    url_publica = os.environ.get("RENDER_EXTERNAL_URL")
    if not url_publica:
        return
    time.sleep(120)
    while True:
        try: requests.get(url_publica)
        except: pass
        time.sleep(600)

if __name__ == '__main__':
    print("🚀 A iniciar ecossistema de rastreamento...")
    iniciar_banco()
    threading.Thread(target=loop_auto_ping, daemon=True).start()
    subprocess.Popen([sys.executable, "-u", "bot.py"])
    subprocess.Popen([sys.executable, "-u", "scraper.py"])
    porta = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=porta)
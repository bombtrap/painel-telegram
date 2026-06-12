import os
import subprocess
import psycopg2
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")

def inicializar_banco():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # AQUI FOI REMOVIDO O 'DROP TABLE'. AGORA É 100% PERSISTENTE!
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS radares (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(50),
                origem VARCHAR(10),
                destino VARCHAR(10),
                alternativo VARCHAR(10),
                max_paradas INT DEFAULT 0,
                skip_principal VARCHAR(5),
                paradas_principal INT,
                skip_alternativa VARCHAR(5) DEFAULT 'nao',
                data_partida VARCHAR(20),
                datas_flexiveis BOOLEAN,
                dias_antes INT,
                dias_depois INT,
                preco_alvo NUMERIC,
                margem INTEGER,
                alerta_madrugada VARCHAR(20),
                telefone VARCHAR(20)
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Base de dados verificada e blindada (Persistência Ativa)!")
    except Exception as e:
        print(f"❌ Erro no banco: {e}")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/salvar', methods=['POST'])
def salvar_radar():
    dados = request.json
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO radares (
                chat_id, origem, destino, alternativo, skip_principal, paradas_principal,
                data_partida, datas_flexiveis, dias_antes, dias_depois,
                preco_alvo, margem, alerta_madrugada, telefone
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(dados['chat_id']), dados['origem'], dados['destino'], dados.get('alternativo', ''), 
            dados['skip_principal'], dados['paradas_principal'],
            dados['data_partida'], dados['datas_flexiveis'], dados['dias_antes'], dados['dias_depois'],
            float(dados['preco_alvo']), int(dados['margem']), dados['alerta_madrugada'], dados['telefone']
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    inicializar_banco()
    subprocess.Popen(["python", "bot.py"])
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
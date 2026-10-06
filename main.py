import os
import subprocess
import psycopg2
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 🔒 Trava de Segurança (Whitelist)
MEU_ID_PERMITIDO = "1377560958"

app = Flask(__name__, static_folder='.')
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")

def inicializar_banco():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 1. Cria a tabela inteira caso o banco esteja vazio (instalação do zero)
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

        # 2. 🚀 LÓGICA DE ATUALIZAÇÃO: Verifica se a coluna de memória já existe
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='radares' AND column_name='ultimo_preco_encontrado'")
        if not cursor.fetchone():
            # Se não existir, ele injeta a coluna nova na tabela antiga sem apagar seus dados
            cursor.execute("ALTER TABLE radares ADD COLUMN ultimo_preco_encontrado NUMERIC")
            conn.commit()
            print("🧠 Coluna de memória (ultimo_preco_encontrado) adicionada com sucesso!")

        cursor.close()
        conn.close()
        print("✅ Base de dados verificada e blindada (Persistência Ativa)!")
    except Exception as e:
        print(f"❌ Erro no banco: {e}")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# 🚀 NOVO: Rota para buscar os dados de um radar específico (Edição)
@app.route('/api/radar/<int:id>', methods=['GET'])
def get_radar(id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, origem, destino, alternativo, max_paradas, skip_principal, 
                   paradas_principal, skip_alternativa, data_partida, datas_flexiveis, 
                   dias_antes, dias_depois, preco_alvo, margem, alerta_madrugada, telefone 
            FROM radares WHERE id = %s
        """, (id,))
        linha = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if linha:
            radar = {
                "id": linha[0], "origem": linha[1], "destino": linha[2], "alternativo": linha[3],
                "max_paradas": linha[4], "skip_principal": linha[5], "paradas_principal": linha[6],
                "skip_alternativa": linha[7], "data_partida": linha[8], "datas_flexiveis": linha[9],
                "dias_antes": linha[10], "dias_depois": linha[11], "preco_alvo": float(linha[12]),
                "margem": linha[13], "alerta_madrugada": linha[14], "telefone": linha[15]
            }
            return jsonify(radar), 200
        return jsonify({"erro": "Radar não encontrado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/salvar', methods=['POST'])
def salvar_radar():
    dados = request.json
    
    # 🛡️ BARREIRA DE ACESSO AQUI: Bloqueia quem não for você antes de chegar no banco
    if str(dados.get('chat_id')) != MEU_ID_PERMITIDO:
        print(f"⚠️️ Tentativa de acesso bloqueada! ID: {dados.get('chat_id')}")
        return jsonify({"erro": "Acesso negado. Bot privado / Sem créditos disponíveis."}), 403

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 🚀 ATUALIZADO: Se o formulário enviar um 'id', é Edição (UPDATE)
        if 'id' in dados and dados['id']:
            cursor.execute("""
                UPDATE radares SET 
                    origem = %s, destino = %s, alternativo = %s, skip_principal = %s, paradas_principal = %s,
                    data_partida = %s, datas_flexiveis = %s, dias_antes = %s, dias_depois = %s,
                    preco_alvo = %s, margem = %s, alerta_madrugada = %s, telefone = %s
                WHERE id = %s AND chat_id = %s
            """, (
                dados['origem'], dados['destino'], dados.get('alternativo', ''), 
                dados['skip_principal'], dados['paradas_principal'],
                dados['data_partida'], dados['datas_flexiveis'], dados['dias_antes'], dados['dias_depois'],
                float(dados['preco_alvo']), int(dados['margem']), dados['alerta_madrugada'], dados['telefone'],
                dados['id'], str(dados['chat_id'])
            ))
        else:
            # Se não enviar 'id', é um radar Novo (INSERT)
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
    subprocess.Popen(["python", "scraper.py"])
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
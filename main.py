def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Buscando a variável direto aqui dentro para garantir que pegou o valor fresco
            db_url = os.getenv("DATABASE_URL")
            
            if not db_url:
                print("🚨 [ERRO CRÍTICO] A variável DATABASE_URL está completamente VAZIA no Render!")
                self.send_response(500)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b"Erro: DATABASE_URL nao configurada no Render.")
                return

            dados = json.loads(post_data.decode('utf-8'))
            chat_id = dados.get("chat_id")
            origem = dados.get("origem")
            destino = dados.get("destino")
            preco_maximo = dados.get("preco_maximo")
            
            if chat_id and origem and destino and preco_maximo:
                # Usa a variável db_url que validamos acima
                conn = psycopg2.connect(db_url)
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
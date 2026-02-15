import os
import time
import json
import jwt
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-secreta-padrao-demo")

# Configuração do Banco de Dados (MariaDB/MySQL)
def normalize_db_url(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
        scheme = parsed.scheme.lower()
        # Força uso do dialeto MariaDB com pymysql, compatível com MariaDB 10.x/11.x
        if scheme.startswith("mysql"):
            scheme = "mariadb+pymysql"
        elif scheme == "mariadb":
            scheme = "mariadb+pymysql"
        elif scheme == "mariadb+pymysql":
            scheme = scheme
        else:
            # mantém, mas deixa como está para outros bancos
            scheme = parsed.scheme
        return urlunparse(parsed._replace(scheme=scheme))
    except Exception:
        return raw_url

DATABASE_URL = normalize_db_url(os.getenv("DATABASE_URL") or "")
engine = None
if DATABASE_URL and DATABASE_URL.strip():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as e:
        print(f"Erro ao configurar DB: {e}")

# Configuração Mock API
API_TOKEN = os.getenv("API_TOKEN", "token-ficticio-123")
MOCK_API_BASE_URL = "https://jsonplaceholder.typicode.com" # Usando JSONPlaceholder para simular

# -------------------------------------------------------------------
# Helper Functions (Lógica das Perguntas)
# -------------------------------------------------------------------

# Pergunta 7: Normalização de Usuários
def normalize_users(input_list):
    normalized = []
    for user in input_list:
        try:
            user_id = int(user.get('id'))
        except (ValueError, TypeError):
            continue
        
        name = user.get('name', '').strip()
        name = ' '.join(name.split())
        name = ' '.join(word.capitalize() for word in name.split())
        
        email = user.get('email', '').strip().lower()
        
        active_val = user.get('active')
        if isinstance(active_val, bool):
            active = active_val
        elif isinstance(active_val, str):
            active = active_val.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(active_val, (int, float)):
            active = bool(active_val)
        else:
            active = False
            
        tags_val = user.get('tags', [])
        if isinstance(tags_val, str):
            tags = [t.strip().lower() for t in tags_val.split(',') if t.strip()]
        elif isinstance(tags_val, (list, tuple)):
            tags = [str(t).strip().lower() for t in tags_val if t]
        else:
            tags = []
        tags = sorted(list(set(tags)))
        
        normalized.append({
            'id': user_id,
            'name': name,
            'email': email,
            'active': active,
            'tags': tags
        })
    return normalized

# Pergunta 8: Deep Key Map
def deep_key_map(obj, key_fn, max_depth=float('inf'), current_depth=0):
    if current_depth >= max_depth:
        return obj
    
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            new_key = key_fn(k)
            new_obj[new_key] = deep_key_map(v, key_fn, max_depth, current_depth + 1)
        return new_obj
    elif isinstance(obj, list):
        return [deep_key_map(item, key_fn, max_depth, current_depth + 1) for item in obj]
    else:
        return obj

def snake_to_camel(snake_str):
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def ensure_sales_orders_exists():
    if not engine:
        return {"created": False, "seeded": False}
    created = False
    seeded = False
    try:
        # Usa transação explícita para garantir commits
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS Sales_Orders (
                    OrderID INT AUTO_INCREMENT PRIMARY KEY,
                    OrderDate DATE NOT NULL,
                    Status VARCHAR(20) NOT NULL,
                    CustomerName VARCHAR(100) NOT NULL,
                    Amount DECIMAL(10,2) NOT NULL,
                    INDEX idx_status_orderdate (Status, OrderDate)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            # Detecta se a tabela estava vazia
            cnt = conn.execute(text("SELECT COUNT(*) FROM Sales_Orders")).scalar()
            if cnt == 0:
                from datetime import date, timedelta
                today = date.today()
                rows = [
                    {"OrderDate": (today - timedelta(days=10)).isoformat(), "Status": "PENDING", "CustomerName": "Alice", "Amount": 150.00},
                    {"OrderDate": (today - timedelta(days=9)).isoformat(),  "Status": "PENDING", "CustomerName": "Bruno", "Amount": 200.50},
                    {"OrderDate": (today - timedelta(days=8)).isoformat(),  "Status": "PROCESSED", "CustomerName": "Carla", "Amount": 75.25},
                    {"OrderDate": (today - timedelta(days=7)).isoformat(),  "Status": "PENDING", "CustomerName": "Diego", "Amount": 1200.00},
                    {"OrderDate": (today - timedelta(days=6)).isoformat(),  "Status": "PENDING", "CustomerName": "Eva", "Amount": 30.00},
                    {"OrderDate": (today - timedelta(days=5)).isoformat(),  "Status": "PROCESSED", "CustomerName": "Fábio", "Amount": 48.90},
                    {"OrderDate": (today - timedelta(days=4)).isoformat(),  "Status": "PENDING", "CustomerName": "Gisele", "Amount": 320.00},
                    {"OrderDate": (today - timedelta(days=3)).isoformat(),  "Status": "PENDING", "CustomerName": "Heitor", "Amount": 89.99},
                    {"OrderDate": (today - timedelta(days=2)).isoformat(),  "Status": "PROCESSED", "CustomerName": "Irene", "Amount": 10.00},
                    {"OrderDate": (today - timedelta(days=1)).isoformat(),  "Status": "PENDING", "CustomerName": "João", "Amount": 999.99},
                ]
                conn.execute(text("""
                    INSERT INTO Sales_Orders (OrderDate, Status, CustomerName, Amount)
                    VALUES (:OrderDate, :Status, :CustomerName, :Amount)
                """), rows)
                seeded = True
        # Se chegamos aqui sem erro, a tabela existe
        created = True
    except Exception as e:
        print(f"Erro ao criar/semear Sales_Orders: {e}")
    return {"created": created, "seeded": seeded}

def ensure_relationships_exists():
    if not engine:
        return {"created": False, "seeded": False}
    created = False
    seeded = False
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS Relacionamentos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    id_origem INT NOT NULL,
                    id_destino INT NOT NULL,
                    tipo_relacao VARCHAR(50) NOT NULL,
                    INDEX idx_rel_origem (id_origem),
                    INDEX idx_rel_destino (id_destino)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            cnt = conn.execute(text("SELECT COUNT(*) FROM Relacionamentos")).scalar()
            if cnt == 0:
                rows = [
                    {"id_origem": 1, "id_destino": 2, "tipo_relacao": "amigo"},
                    {"id_origem": 2, "id_destino": 3, "tipo_relacao": "amigo"},
                    {"id_origem": 3, "id_destino": 4, "tipo_relacao": "amigo"},
                    {"id_origem": 1, "id_destino": 5, "tipo_relacao": "seguidor"},
                    {"id_origem": 5, "id_destino": 6, "tipo_relacao": "seguidor"},
                    {"id_origem": 2, "id_destino": 5, "tipo_relacao": "colega"},
                    {"id_origem": 4, "id_destino": 6, "tipo_relacao": "colega"},
                    {"id_origem": 6, "id_destino": 7, "tipo_relacao": "amigo"},
                    {"id_origem": 3, "id_destino": 7, "tipo_relacao": "seguidor"},
                    {"id_origem": 7, "id_destino": 8, "tipo_relacao": "amigo"}
                ]
                conn.execute(text("""
                    INSERT INTO Relacionamentos (id_origem, id_destino, tipo_relacao)
                    VALUES (:id_origem, :id_destino, :tipo_relacao)
                """), rows)
                seeded = True
        created = True
    except Exception as e:
        print(f"Erro ao criar/semear Relacionamentos: {e}")
    return {"created": created, "seeded": seeded}

def get_sales_orders():
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    OrderID,
                    OrderDate,
                    Status,
                    CustomerName,
                    Amount
                FROM Sales_Orders
                ORDER BY OrderDate DESC, OrderID DESC
            """))
            return [dict(row) for row in result.mappings()]
    except Exception as e:
        print(f"Erro ao carregar Sales_Orders: {e}")
        return []

# Pergunta 6: Mock API Logic
def get_orders_page(status='PENDING', page=1, per_page=20):
    if not engine:
        return {"data": [], "next_page": None}
    try:
        with engine.connect() as conn:
            offset = (page - 1) * per_page
            result = conn.execute(text("""
                SELECT 
                    OrderID AS id,
                    Status AS status,
                    Amount,
                    OrderDate,
                    CustomerName
                FROM Sales_Orders
                WHERE Status = :status
                ORDER BY OrderDate, OrderID
                LIMIT :limit OFFSET :offset
            """), {"status": status, "limit": per_page, "offset": offset})
            rows = list(result.mappings())
            data = [dict(row) for row in rows]
            next_page = page + 1 if len(data) == per_page else None
            return {"data": data, "next_page": next_page}
    except Exception as e:
        print(f"Erro ao buscar pedidos da API mock: {e}")
        return {"data": [], "next_page": None}

def mock_api_get_pending(page=1, per_page=20):
    return get_orders_page('PENDING', page=page, per_page=per_page)

def mock_api_confirm(order_id, idempotency_key):
    import random
    if random.random() < 0.2:
        raise requests.exceptions.HTTPError("500 Server Error")
    if not engine:
        return {"status": "confirmed", "order_id": order_id}
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE Sales_Orders
                SET Status = 'PROCESSED'
                WHERE OrderID = :order_id AND Status = 'PENDING'
            """), {"order_id": order_id})
        return {"status": "confirmed", "order_id": order_id}
    except Exception as e:
        raise requests.exceptions.HTTPError(str(e))

# -------------------------------------------------------------------
# Rotas
# -------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/responses')
def responses():
    # Renderiza como HTML puro, ignorando sintaxe Jinja2 no conteúdo
    with open('templates/responses.html', 'r', encoding='utf-8') as f:
        content = f.read()
    return content

@app.route('/responses/notion')
def responses_notion():
    try:
        with open('Responses-notion.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Erro ao carregar Notion export: {e}", 500

# Demo 1: OAuth Flow
@app.route('/demo/1')
def demo_oauth():
    return render_template('demo_oauth.html')

@app.route('/api/oauth/token', methods=['POST'])
def oauth_token():
    # Simula geração de token
    expiration = datetime.now(timezone.utc) + timedelta(seconds=60)
    payload = {
        "sub": "1234567890",
        "name": "John Doe",
        "iat": datetime.now(timezone.utc),
        "exp": expiration,
        "scope": "read write"
    }
    access_token = jwt.encode(payload, app.secret_key, algorithm="HS256")
    
    refresh_expiration = datetime.now(timezone.utc) + timedelta(days=7)
    refresh_payload = {
        "sub": "1234567890",
        "type": "refresh",
        "exp": refresh_expiration
    }
    refresh_token = jwt.encode(refresh_payload, app.secret_key + "_refresh", algorithm="HS256")
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 60
    })

@app.route('/api/oauth/refresh', methods=['POST'])
def oauth_refresh():
    refresh_token = request.json.get('refresh_token')
    if not refresh_token:
        return jsonify({"error": "Refresh token required"}), 400
    
    try:
        # Decodifica e valida refresh token
        decoded = jwt.decode(refresh_token, app.secret_key + "_refresh", algorithms=["HS256"])
        if decoded.get("type") != "refresh":
             return jsonify({"error": "Invalid token type"}), 400
             
        # Gera novo access token
        new_expiration = datetime.now(timezone.utc) + timedelta(seconds=60)
        new_payload = {
            "sub": decoded["sub"],
            "name": "John Doe",
            "iat": datetime.now(timezone.utc),
            "exp": new_expiration,
            "scope": "read write"
        }
        new_access_token = jwt.encode(new_payload, app.secret_key, algorithm="HS256")
        
        return jsonify({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 60
        })
        
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 401
# Demo 5: SQL Update
@app.route('/demo/5', methods=['GET', 'POST'])
def demo_sql_update():
    db_connected = False
    db_version = None
    conn_error = None
    seed_info = None
    orders = []
    if not engine:
        conn_error = "Nenhum DATABASE_URL configurado."
        return render_template('demo_sql_update.html', db_connected=False, db_version=None, conn_error=conn_error, result=None, seeded=None)
    else:
        # Valida conexão e obtém versão do servidor
        try:
            with engine.connect() as conn:
                ver = conn.execute(text("SELECT VERSION()")).scalar()
                db_version = ver
                db_connected = True
            # Garante a existência da tabela e dados de exemplo
            seed_info = ensure_sales_orders_exists()
            orders = get_sales_orders()
        except Exception as e:
            conn_error = str(e)
            db_connected = False
            return render_template('demo_sql_update.html', db_connected=False, db_version=None, conn_error=conn_error, result=None, seeded=None)

    result_msg = None
    affected_rows = 0
    
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'reset':
            try:
                with engine.begin() as conn:
                    result = conn.execute(text("""
                        UPDATE Sales_Orders
                        SET Status = 'PENDING'
                        WHERE Status = 'PROCESSED'
                    """))
                    affected_rows = result.rowcount
                    result_msg = f"{affected_rows} registros PROCESSED foram resetados para PENDING."
            except SQLAlchemyError as e:
                result_msg = f"Erro de conexão: {str(e)}"
        else:
            cutoff_date = request.form.get('cutoff_date')
            try:
                with engine.connect() as conn:
                    trans = conn.begin()
                    try:
                        # Query parametrizada
                        query = text("""
                            UPDATE Sales_Orders 
                            SET Status = 'PROCESSED' 
                            WHERE Status = 'PENDING' AND OrderDate >= :cutoff_date
                        """)
                        result = conn.execute(query, {"cutoff_date": cutoff_date})
                        affected_rows = result.rowcount
                        trans.commit()
                        result_msg = f"Sucesso! {affected_rows} pedidos atualizados."
                    except Exception as e:
                        trans.rollback()
                        result_msg = f"Erro na transação: {str(e)}"
            except SQLAlchemyError as e:
                 result_msg = f"Erro de conexão: {str(e)}"

        # Atualiza a lista após tentativa de atualização
        orders = get_sales_orders()

    return render_template(
        'demo_sql_update.html',
        db_connected=db_connected,
        db_version=db_version,
        conn_error=conn_error,
        result=result_msg,
        seeded=seed_info if db_connected else None,
        orders=orders
    )

# Demo 6: API Consumption
@app.route('/demo/6')
def demo_api():
    return render_template('demo_api.html')

@app.route('/api/orders', methods=['GET'])
def api_orders():
    status = request.args.get('status', 'pending').upper()
    page = int(request.args.get('page', 1) or 1)
    page_size = int(request.args.get('page_size', 20) or 20)
    data = get_orders_page(status=status, page=page, per_page=page_size)
    return jsonify(data)

@app.route('/api/orders/<int:order_id>/confirm', methods=['POST'])
def api_orders_confirm(order_id):
    idempotency_key = request.headers.get('Idempotency-Key') or hashlib.md5(str(order_id).encode()).hexdigest()
    try:
        mock_api_confirm(order_id, idempotency_key)
        return jsonify({"status": "confirmed", "order_id": order_id})
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders/reset-status', methods=['POST'])
def api_orders_reset_status():
    if not engine:
        return jsonify({"updated": 0, "message": "Banco não configurado"}), 500
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE Sales_Orders
                SET Status = 'PENDING'
                WHERE Status = 'PROCESSED'
            """))
            return jsonify({"updated": result.rowcount})
    except SQLAlchemyError as e:
        return jsonify({"updated": 0, "message": str(e)}), 500

@app.route('/api/process-orders', methods=['POST'])
def process_orders():
    logs = []
    processed_count = 0
    failed_count = 0
    processed_ids = []
    failed_ids = []
    
    try:
        page = 1
        while True:
            logs.append(f"Buscando página {page}...")
            response = mock_api_get_pending(page, per_page=20)
            orders = response.get('data', [])
            
            if not orders:
                logs.append("Nenhum pedido encontrado nesta página.")
                break
                
            for order in orders:
                order_id = order['id']
                logs.append(f"Processando pedido {order_id}...")
                
                # Idempotency Key
                idempotency_key = hashlib.md5(str(order_id).encode()).hexdigest()
                
                # Retry Logic
                success = False
                for attempt in range(1, 4):
                    try:
                        # Mock Confirm Call
                        mock_api_confirm(order_id, idempotency_key)
                        logs.append(f"  -> Pedido {order_id} confirmado (tentativa {attempt}).")
                        success = True
                        processed_count += 1
                        processed_ids.append(order_id)
                        break
                    except Exception as e:
                        logs.append(f"  -> Erro ao confirmar {order_id} (tentativa {attempt}): {str(e)}")
                        time.sleep(0.5) # Backoff simulado
                
                if not success:
                    logs.append(f"  -> Falha definitiva no pedido {order_id}.")
                    failed_count += 1
                    failed_ids.append(order_id)
            
            if not response.get('next_page'):
                break
            page = response['next_page']
            
    except Exception as e:
        logs.append(f"Erro geral: {str(e)}")
        
    return jsonify({
        "logs": logs,
        "summary": {
            "processed": processed_count,
            "failed": failed_count
        },
        "details": {
            "processed_ids": processed_ids,
            "failed_ids": failed_ids
        }
    })

# Demo 7: Normalization
@app.route('/demo/7', methods=['GET', 'POST'])
def demo_normalization():
    output = None
    input_text = ""
    if request.method == 'POST':
        input_text = request.form.get('json_input')
        try:
            data = json.loads(input_text)
            output = normalize_users(data)
        except json.JSONDecodeError:
            flash("JSON inválido!", "danger")
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")
            
    return render_template('demo_normalization.html', output=output, input_text=input_text)

# Demo 8: Deep Key Map
@app.route('/demo/8', methods=['GET', 'POST'])
def demo_deepkey():
    output = None
    input_text = ""
    max_depth = 10
    if request.method == 'POST':
        input_text = request.form.get('json_input')
        max_depth = int(request.form.get('max_depth', 10))
        try:
            data = json.loads(input_text)
            # Usando snake_to_camel como key_fn exemplo
            output = deep_key_map(data, snake_to_camel, max_depth=max_depth)
        except json.JSONDecodeError:
            flash("JSON inválido!", "danger")
        except Exception as e:
            flash(f"Erro: {str(e)}", "danger")
            
    return render_template('demo_deepkey.html', output=output, input_text=input_text, max_depth=max_depth)

# Demo 3: Recursive CTE
@app.route('/demo/3', methods=['GET', 'POST'])
def demo_cte():
    if not engine:
        flash("Banco de dados não configurado (DATABASE_URL ausente).", "warning")
        return render_template('demo_cte.html', db_connected=False)
    
    ensure_relationships_exists()
        
    results = None
    error = None
    depth_limit = 5
    user_summary = None
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        try:
            depth_limit = int(request.form.get('depth_limit', 5))
        except (TypeError, ValueError):
            depth_limit = 5
        try:
            with engine.connect() as conn:
                query = text("""
                    WITH RECURSIVE relationship_chain AS (
                        SELECT 
                            id_origem AS start_id,
                            id_origem AS current_id,
                            id_destino AS next_id,
                            tipo_relacao,
                            1 AS depth,
                            CAST(id_origem AS CHAR(200)) AS path
                        FROM Relacionamentos
                        WHERE id_origem = :user_id
                        
                        UNION ALL
                        
                        SELECT 
                            rc.start_id,
                            rc.next_id AS current_id,
                            r.id_destino AS next_id,
                            r.tipo_relacao,
                            rc.depth + 1,
                            CONCAT(rc.path, '->', r.id_destino)
                        FROM relationship_chain rc
                        JOIN Relacionamentos r ON rc.next_id = r.id_origem
                        WHERE rc.depth < :max_depth
                    )
                    SELECT * FROM relationship_chain;
                """)
                result_proxy = conn.execute(query, {"user_id": user_id, "max_depth": depth_limit})
                results = [dict(row) for row in result_proxy.mappings()]
                summary_query = text("""
                    SELECT 
                        usuario, 
                        SUM(saidas) AS saidas, 
                        SUM(entradas) AS entradas, 
                        SUM(saidas + entradas) AS total_conexoes 
                    FROM ( 
                        SELECT id_origem AS usuario, COUNT(*) AS saidas, 0 AS entradas 
                        FROM Relacionamentos 
                        WHERE id_origem = :user_id 
                        GROUP BY id_origem 
                        
                        UNION ALL 
                        
                        SELECT id_destino AS usuario, 0 AS saidas, COUNT(*) AS entradas 
                        FROM Relacionamentos 
                        WHERE id_destino = :user_id 
                        GROUP BY id_destino 
                    ) AS combined 
                    GROUP BY usuario 
                    ORDER BY usuario
                """)
                summary_result = conn.execute(summary_query, {"user_id": user_id}).mappings().first()
                if summary_result:
                    user_summary = dict(summary_result)
        except Exception as e:
            error = f"Erro na execução SQL (Verifique se a tabela 'Relacionamentos' existe): {str(e)}"

    return render_template('demo_cte.html', db_connected=True, results=results, error=error, depth_limit=depth_limit, user_summary=user_summary)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

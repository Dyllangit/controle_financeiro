from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import date, datetime, timedelta
from typing import Optional
import os
import pymysql.cursors
import bcrypt
import jwt

SECRET_KEY = os.environ.get("SECRET_KEY", "mude-essa-chave-em-producao-123!")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 7 dias

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ─── Banco de Dados ───────────────────────────────────────────────────────────

def get_db():
    return pymysql.connect(
        host="financeiro-financeiro123.d.aivencloud.com",
        user="avnadmin",
        password=os.environ.get("DB_PASSWORD"),
        database="defaultdb",
        port=21040,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# ─── JWT ─────────────────────────────────────────────────────────────────────

def criar_token(usuario_id: int, email: str) -> str:
    payload = {
        "sub": str(usuario_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")

# ─── Modelos ──────────────────────────────────────────────────────────────────

class Registro(BaseModel):
    nome: str
    email: str
    senha: str

class Login(BaseModel):
    email: str
    senha: str

class Gasto(BaseModel):
    descricao: str
    valor: float
    tipo: str
    categoria: str
    data: date
    banco_id: int

class Meta(BaseModel):
    nome: str
    alvo: float

class Deposito(BaseModel):
    valor: float

class Config(BaseModel):
    saldo: float
    limite_credito: float

class Banco(BaseModel):
    banco_lista_id: int
    saldo: float = 0
    limite_credito: float = 0

class Categoria(BaseModel):
    nome: str

# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/registrar")
def registrar(dados: Registro):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email=%s", (dados.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    hash_senha = bcrypt.hashpw(dados.senha.encode(), bcrypt.gensalt()).decode()
    cursor.execute(
        "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s)",
        (dados.nome, dados.email, hash_senha)
    )
    usuario_id = cursor.lastrowid
    # Criar configuração inicial para o novo usuário
    cursor.execute(
        "INSERT INTO configuracoes (usuario_id, saldo, limite_credito) VALUES (%s, 0, 0)",
        (usuario_id,)
    )
    # Inserir categorias padrão para o novo usuário
    cats_padrao = ['Pessoal', 'Amigos', 'Conta', 'Alimentação', 'Transporte', 'Saúde', 'Lazer', 'Outro']
    for cat in cats_padrao:
        cursor.execute("INSERT INTO categorias (nome, usuario_id) VALUES (%s, %s)", (cat, usuario_id))
    token = criar_token(usuario_id, dados.email)
    return {"token": token, "nome": dados.nome, "email": dados.email}

@app.post("/login")
def login(dados: Login):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE email=%s", (dados.email,))
    usuario = cursor.fetchone()
    if not usuario or not bcrypt.checkpw(dados.senha.encode(), usuario["senha_hash"].encode()):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    token = criar_token(usuario["id"], usuario["email"])
    return {"token": token, "nome": usuario["nome"], "email": usuario["email"]}

@app.get("/me")
def me(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, nome, email FROM usuarios WHERE id=%s", (usuario_id,))
    return cursor.fetchone()

# ─── Bancos ───────────────────────────────────────────────────────────────────

@app.get("/bancos")
def listar_bancos(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    # Usamos JOIN para pegar o nome da tabela oficial
    cursor.execute("""
        SELECT b.id, b.saldo, b.limite_credito, bl.nome, bl.id as banco_lista_id
        FROM bancos b
        JOIN bancos_lista bl ON b.banco_lista_id = bl.id
        WHERE b.usuario_id=%s ORDER BY bl.nome
    """, (usuario_id,))
    return cursor.fetchall()

@app.post("/bancos")
def criar_banco(b: Banco, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO bancos (banco_lista_id, saldo, limite_credito, usuario_id) VALUES (%s, %s, %s, %s)",
        (b.banco_lista_id, b.saldo, b.limite_credito, usuario_id)
    )
    return {"id": cursor.lastrowid}

@app.put("/bancos/{id}")
def atualizar_banco(id: int, b: Banco, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE bancos SET nome=%s, saldo=%s, limite_credito=%s WHERE id=%s AND usuario_id=%s",
        (b.nome, b.saldo, b.limite_credito, id, usuario_id)
    )
    return {"ok": True}

@app.delete("/bancos/{id}")
def deletar_banco(id: int, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM bancos WHERE id=%s AND usuario_id=%s", (id, usuario_id))
    return {"ok": True}

# ─── Categorias ───────────────────────────────────────────────────────────────

@app.get("/categorias")
def listar_categorias(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categorias WHERE usuario_id=%s ORDER BY nome", (usuario_id,))
    return cursor.fetchall()

@app.post("/categorias")
def criar_categoria(c: Categoria, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO categorias (nome, usuario_id) VALUES (%s, %s)", (c.nome, usuario_id))
    return {"id": cursor.lastrowid}

@app.delete("/categorias/{id}")
def deletar_categoria(id: int, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM categorias WHERE id=%s AND usuario_id=%s", (id, usuario_id))
    return {"ok": True}

# ─── Gastos ───────────────────────────────────────────────────────────────────

@app.get("/gastos")
def listar_gastos(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT g.*, b.nome as banco_nome
        FROM gastos g
        LEFT JOIN bancos b ON g.banco_id = b.id
        WHERE g.usuario_id=%s
        ORDER BY g.data DESC
    """, (usuario_id,))
    return cursor.fetchall()

@app.post("/gastos")
def criar_gasto(g: Gasto, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO gastos (descricao, valor, tipo, categoria, data, banco_id, usuario_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (g.descricao, g.valor, g.tipo, g.categoria, g.data, g.banco_id, usuario_id)
    )
    return {"id": cursor.lastrowid}

@app.delete("/gastos/{id}")
def deletar_gasto(id: int, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM gastos WHERE id=%s AND usuario_id=%s", (id, usuario_id))
    return {"ok": True}

# ─── Metas ────────────────────────────────────────────────────────────────────

@app.get("/metas")
def listar_metas(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM metas WHERE usuario_id=%s", (usuario_id,))
    return cursor.fetchall()

@app.post("/metas")
def criar_meta(m: Meta, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO metas (nome, alvo, usuario_id) VALUES (%s,%s,%s)", (m.nome, m.alvo, usuario_id))
    return {"id": cursor.lastrowid}

@app.post("/metas/{id}/depositar")
def depositar(id: int, d: Deposito, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE metas SET poupado = LEAST(alvo, poupado + %s) WHERE id=%s AND usuario_id=%s",
        (d.valor, id, usuario_id)
    )
    return {"ok": True}

@app.delete("/metas/{id}")
def deletar_meta(id: int, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM metas WHERE id=%s AND usuario_id=%s", (id, usuario_id))
    return {"ok": True}

# ─── Configurações ────────────────────────────────────────────────────────────

@app.get("/config")
def get_config(usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM configuracoes WHERE usuario_id=%s", (usuario_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO configuracoes (usuario_id, saldo, limite_credito) VALUES (%s, 0, 0)", (usuario_id,))
        return {"saldo": 0, "limite_credito": 0}
    return row

@app.put("/config")
def salvar_config(c: Config, usuario_id: int = Depends(verificar_token)):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE configuracoes SET saldo=%s, limite_credito=%s WHERE usuario_id=%s",
        (c.saldo, c.limite_credito, usuario_id)
    )
    return {"ok": True}

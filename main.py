from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
import os
import pymysql.cursors


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- Modelos ---
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
    nome: str
    saldo: float = 0
    limite_credito: float = 0

class Categoria(BaseModel):
    nome: str

# --- Bancos ---
@app.get("/bancos")
def listar_bancos():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM bancos ORDER BY nome")
    return cursor.fetchall()

@app.post("/bancos")
def criar_banco(b: Banco):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO bancos (nome, saldo, limite_credito) VALUES (%s, %s, %s)",
        (b.nome, b.saldo, b.limite_credito)
    )
    return {"id": cursor.lastrowid}

@app.put("/bancos/{id}")
def atualizar_banco(id: int, b: Banco):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE bancos SET nome=%s, saldo=%s, limite_credito=%s WHERE id=%s",
        (b.nome, b.saldo, b.limite_credito, id)
    )
    return {"ok": True}

@app.delete("/bancos/{id}")
def deletar_banco(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM bancos WHERE id=%s", (id,))
    return {"ok": True}

# --- Categorias ---
@app.get("/categorias")
def listar_categorias():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categorias ORDER BY nome")
    return cursor.fetchall()

@app.post("/categorias")
def criar_categoria(c: Categoria):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO categorias (nome) VALUES (%s)", (c.nome,))
    return {"id": cursor.lastrowid}

@app.delete("/categorias/{id}")
def deletar_categoria(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM categorias WHERE id=%s", (id,))
    return {"ok": True}

# --- Gastos ---
@app.get("/gastos")
def listar_gastos():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT g.*, b.nome as banco_nome
        FROM gastos g
        LEFT JOIN bancos b ON g.banco_id = b.id
        ORDER BY g.data DESC
    """)
    return cursor.fetchall()

@app.post("/gastos")
def criar_gasto(g: Gasto):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO gastos (descricao, valor, tipo, categoria, data, banco_id) VALUES (%s,%s,%s,%s,%s,%s)",
        (g.descricao, g.valor, g.tipo, g.categoria, g.data, g.banco_id)
    )
    return {"id": cursor.lastrowid}

@app.delete("/gastos/{id}")
def deletar_gasto(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM gastos WHERE id=%s", (id,))
    return {"ok": True}

# --- Metas ---
@app.get("/metas")
def listar_metas():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM metas")
    return cursor.fetchall()

@app.post("/metas")
def criar_meta(m: Meta):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO metas (nome, alvo) VALUES (%s,%s)", (m.nome, m.alvo))
    return {"id": cursor.lastrowid}

@app.post("/metas/{id}/depositar")
def depositar(id: int, d: Deposito):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE metas SET poupado = LEAST(alvo, poupado + %s) WHERE id=%s", (d.valor, id))
    return {"ok": True}

@app.delete("/metas/{id}")
def deletar_meta(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM metas WHERE id=%s", (id,))
    return {"ok": True}

# --- Configurações (mantido para compatibilidade) ---
@app.get("/config")
def get_config():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM configuracoes WHERE id=1")
    return cursor.fetchone()

@app.put("/config")
def salvar_config(c: Config):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE configuracoes SET saldo=%s, limite_credito=%s WHERE id=1",
        (c.saldo, c.limite_credito)
    )
    return {"ok": True}

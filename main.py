from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
import mysql.connector

app = FastAPI()

# Permite o navegador chamar a API
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    return mysql.connector.connect(
        host="localhost", 
        user="root", 
        password="12345", 
        database="financas",
        # Adicione esta linha abaixo:
        collation="utf8mb4_general_ci" 
    )
# --- Modelos ---
class Gasto(BaseModel):
    descricao: str
    valor: float
    tipo: str
    categoria: str
    data: date

class Meta(BaseModel):
    nome: str
    alvo: float

class Deposito(BaseModel):
    valor: float

class Config(BaseModel):
    saldo: float
    limite_credito: float

# --- Gastos ---
@app.get("/gastos")
def listar_gastos():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM gastos ORDER BY data DESC")
    return cursor.fetchall()

@app.post("/gastos")
def criar_gasto(g: Gasto):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO gastos (descricao, valor, tipo, categoria, data) VALUES (%s,%s,%s,%s,%s)",
                   (g.descricao, g.valor, g.tipo, g.categoria, g.data))
    db.commit()
    return {"id": cursor.lastrowid}

@app.delete("/gastos/{id}")
def deletar_gasto(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM gastos WHERE id=%s", (id,))
    db.commit()
    return {"ok": True}

# --- Metas ---
@app.get("/metas")
def listar_metas():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM metas")
    return cursor.fetchall()

@app.post("/metas")
def criar_meta(m: Meta):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO metas (nome, alvo) VALUES (%s,%s)", (m.nome, m.alvo))
    db.commit()
    return {"id": cursor.lastrowid}

@app.post("/metas/{id}/depositar")
def depositar(id: int, d: Deposito):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE metas SET poupado = LEAST(alvo, poupado + %s) WHERE id=%s", (d.valor, id))
    db.commit()
    return {"ok": True}

@app.delete("/metas/{id}")
def deletar_meta(id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM metas WHERE id=%s", (id,))
    db.commit()
    return {"ok": True}

# --- Configurações ---
@app.get("/config")
def get_config():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM configuracoes WHERE id=1")
    return cursor.fetchone()

@app.put("/config")
def salvar_config(c: Config):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE configuracoes SET saldo=%s, limite_credito=%s WHERE id=1", (c.saldo, c.limite_credito))
    db.commit()
    return {"ok": True}
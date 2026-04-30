"""
OMS Industries — Sistema Assemblaggio EMAX2
Backend FastAPI — VERSIONE CLOUD (Railway + PostgreSQL)
Tutti gli step avvitatore sono gestiti come verifica visiva.
Nessun hardware richiesto — accessibile da qualsiasi browser.
"""

import hashlib
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ============================================================
# CONFIGURAZIONE
# Railway inietta automaticamente DATABASE_URL per PostgreSQL.
# Se non presente, usa SQLite locale (sviluppo).
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgresql")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    print("DATABASE_URL non trovato — uso SQLite locale.")

DB_PATH = Path("oms_assemblaggio.db")

# ============================================================
# DATABASE — supporto PostgreSQL e SQLite
# ============================================================

def get_db():
    if USE_POSTGRES:
        url = DATABASE_URL.replace("postgresql://", "postgres://") \
                          .replace("postgres://", "postgresql://")
        conn = psycopg2.connect(DATABASE_URL,
                                cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()


def db_execute(conn, query, params=()):
    """Esegue query compatibile con PostgreSQL e SQLite."""
    if USE_POSTGRES:
        query = query.replace("?", "%s")
        query = query.replace("datetime('now')", "NOW()")
        query = query.replace("DATE(", "DATE(")
    cur = conn.cursor()
    cur.execute(query, params)
    return cur


def db_fetchone(cur):
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def db_fetchall(cur):
    return [dict(r) for r in cur.fetchall()]


def init_db():
    """Inizializza il database con schema e dati demo."""
    schema = Path("schema.sql")
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM operatori")
            conn.close()
            print("Database PostgreSQL già inizializzato.")
        except Exception:
            print("Inizializzazione database PostgreSQL...")
            if schema.exists():
                conn = psycopg2.connect(DATABASE_URL)
                # Converti SQLite → PostgreSQL
                sql = schema.read_text(encoding="utf-8")
                sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT",
                                  "SERIAL PRIMARY KEY")
                sql = sql.replace("TEXT", "TEXT")
                sql = sql.replace("REAL", "NUMERIC")
                sql = sql.replace("datetime('now')", "NOW()")
                sql = sql.replace("PRAGMA journal_mode = WAL;", "")
                sql = sql.replace("PRAGMA foreign_keys = ON;", "")
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
                conn.close()
                print("Database PostgreSQL inizializzato.")
    else:
        if not DB_PATH.exists() and schema.exists():
            conn = sqlite3.connect(DB_PATH)
            conn.executescript(schema.read_text(encoding="utf-8"))
            conn.commit()
            conn.close()
            print("Database SQLite inizializzato.")


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


# ============================================================
# MODELLI
# ============================================================

class LoginRequest(BaseModel):
    operatore_id: int
    pin: str

class AvviaSessioneRequest(BaseModel):
    operatore_id: int
    ciclo_id: int

class CompletaStepRequest(BaseModel):
    step_id: int
    esito: str
    valore_letto: Optional[str] = None
    note: Optional[str] = None

class CreaOperatoreRequest(BaseModel):
    nome: str
    cognome: str
    pin: str
    ruolo: str = "operatore"


# ============================================================
# APP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="OMS Industries — Assemblaggio EMAX2 Cloud", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")


# ============================================================
# API
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "db": "postgresql" if USE_POSTGRES else "sqlite",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/operatori")
def lista_operatori(db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT id, nome, cognome, ruolo, attivo FROM operatori WHERE attivo=1 ORDER BY cognome"
    )
    return db_fetchall(cur)

@app.post("/api/operatori", status_code=201)
def crea_operatore(req: CreaOperatoreRequest, db=Depends(get_db)):
    if req.ruolo not in ("operatore", "supervisore", "admin"):
        raise HTTPException(400, "Ruolo non valido.")
    cur = db_execute(db,
        "INSERT INTO operatori (nome, cognome, pin_hash, ruolo) VALUES (?, ?, ?, ?)",
        (req.nome, req.cognome, hash_pin(req.pin), req.ruolo)
    )
    db.commit()
    return {"ok": True}

@app.post("/api/login")
def login(req: LoginRequest, db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT * FROM operatori WHERE id=? AND attivo=1", (req.operatore_id,)
    )
    op = db_fetchone(cur)
    if not op:
        raise HTTPException(401, "Operatore non trovato.")
    if op["pin_hash"] != hash_pin(req.pin):
        raise HTTPException(401, "PIN non corretto.")
    return {
        "ok": True,
        "operatore_id": op["id"],
        "nome": op["nome"],
        "cognome": op["cognome"],
        "ruolo": op["ruolo"]
    }

@app.get("/api/cicli")
def lista_cicli(db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT id, codice, nome, descrizione FROM cicli WHERE attivo=1"
    )
    return db_fetchall(cur)

@app.get("/api/ciclo/{ciclo_id}/step")
def step_ciclo(ciclo_id: int, db=Depends(get_db)):
    cur = db_execute(db,
        """SELECT id, ordine, titolo, istruzione, tipo_avanzamento,
                  codice_atteso, coppia_min_nm, coppia_max_nm, n_avvitature
           FROM step WHERE ciclo_id=? ORDER BY ordine""",
        (ciclo_id,)
    )
    rows = db_fetchall(cur)
    if not rows:
        raise HTTPException(404, "Ciclo non trovato.")
    # Versione cloud: tutti gli step avvitatore → visivo
    for r in rows:
        if r["tipo_avanzamento"] == "avvitatore":
            r["tipo_avanzamento"] = "visivo"
            r["istruzione"] = r["istruzione"] + \
                f" Coppia target: {r['coppia_min_nm']}–{r['coppia_max_nm']} Nm, " \
                f"{r['n_avvitature']} avvitature. Conferma dopo aver eseguito il serraggio."
    return rows

@app.post("/api/sessione/avvia", status_code=201)
def avvia_sessione(req: AvviaSessioneRequest, db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT id FROM sessioni WHERE operatore_id=? AND esito='in_corso'",
        (req.operatore_id,)
    )
    in_corso = db_fetchone(cur)
    if in_corso:
        raise HTTPException(409, f"Sessione già in corso (ID: {in_corso['id']}).")
    cur = db_execute(db,
        "INSERT INTO sessioni (operatore_id, ciclo_id) VALUES (?, ?)",
        (req.operatore_id, req.ciclo_id)
    )
    db.commit()
    if USE_POSTGRES:
        cur2 = db_execute(db, "SELECT lastval()")
        sid = db_fetchone(cur2)["lastval"]
    else:
        sid = cur.lastrowid
    return {"sessione_id": sid, "ok": True}

@app.post("/api/sessione/{sessione_id}/step")
def completa_step(sessione_id: int, req: CompletaStepRequest, db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT * FROM sessioni WHERE id=? AND esito='in_corso'", (sessione_id,)
    )
    if not db_fetchone(cur):
        raise HTTPException(404, "Sessione non trovata o non attiva.")
    cur = db_execute(db,
        "INSERT INTO log_step (sessione_id, step_id, esito, valore_letto, note) VALUES (?,?,?,?,?)",
        (sessione_id, req.step_id, req.esito, req.valore_letto, req.note)
    )
    db.commit()
    if USE_POSTGRES:
        cur2 = db_execute(db, "SELECT lastval()")
        lid = db_fetchone(cur2)["lastval"]
    else:
        lid = cur.lastrowid
    return {"log_step_id": lid, "ok": True}

@app.get("/api/sessione/{sessione_id}")
def stato_sessione(sessione_id: int, db=Depends(get_db)):
    cur = db_execute(db,
        """SELECT s.*, o.nome, o.cognome, c.codice as ciclo_codice, c.nome as ciclo_nome
           FROM sessioni s
           JOIN operatori o ON o.id=s.operatore_id
           JOIN cicli c ON c.id=s.ciclo_id
           WHERE s.id=?""", (sessione_id,)
    )
    sessione = db_fetchone(cur)
    if not sessione:
        raise HTTPException(404, "Sessione non trovata.")
    cur = db_execute(db,
        """SELECT ls.step_id, ls.esito, ls.eseguito_il, st.ordine, st.titolo
           FROM log_step ls JOIN step st ON st.id=ls.step_id
           WHERE ls.sessione_id=? ORDER BY ls.eseguito_il""", (sessione_id,)
    )
    sessione["step_completati"] = db_fetchall(cur)
    sessione["n_step_completati"] = len(sessione["step_completati"])
    return sessione

@app.post("/api/sessione/{sessione_id}/chiudi")
def chiudi_sessione(sessione_id: int, db=Depends(get_db)):
    cur = db_execute(db,
        "SELECT * FROM sessioni WHERE id=? AND esito='in_corso'", (sessione_id,)
    )
    if not db_fetchone(cur):
        raise HTTPException(404, "Sessione non trovata o già chiusa.")
    cur = db_execute(db,
        "SELECT COUNT(*) as n FROM log_step WHERE sessione_id=? AND esito='nok'",
        (sessione_id,)
    )
    n_nok = db_fetchone(cur)["n"]
    esito = "completata" if n_nok == 0 else "errore"
    db_execute(db,
        "UPDATE sessioni SET fine=datetime('now'), esito=? WHERE id=?",
        (esito, sessione_id)
    )
    db.commit()
    return {"ok": True, "esito": esito}

@app.get("/api/dashboard")
def dashboard(data: Optional[str] = None, db=Depends(get_db)):
    if not data:
        data = datetime.now().strftime("%Y-%m-%d")
    cur = db_execute(db,
        "SELECT COUNT(*) as n FROM sessioni WHERE esito='completata' AND DATE(fine)=?", (data,)
    )
    cicli = db_fetchone(cur)["n"]
    cur = db_execute(db,
        "SELECT COUNT(DISTINCT operatore_id) as n FROM sessioni WHERE esito='in_corso'"
    )
    op_attivi = db_fetchone(cur)["n"]
    cur = db_execute(db,
        """SELECT s.id, o.nome, o.cognome, s.inizio, c.codice as ciclo
           FROM sessioni s
           JOIN operatori o ON o.id=s.operatore_id
           JOIN cicli c ON c.id=s.ciclo_id
           WHERE s.esito='in_corso'"""
    )
    sessioni_attive = db_fetchall(cur)
    cur = db_execute(db,
        """SELECT ls.eseguito_il, ls.esito, o.nome, o.cognome, st.titolo, st.ordine
           FROM log_step ls
           JOIN sessioni s ON s.id=ls.sessione_id
           JOIN operatori o ON o.id=s.operatore_id
           JOIN step st ON st.id=ls.step_id
           WHERE DATE(ls.eseguito_il)=?
           ORDER BY ls.eseguito_il DESC LIMIT 50""", (data,)
    )
    log_recente = db_fetchall(cur)
    return {
        "data": data,
        "cicli_completati": cicli,
        "operatori_attivi": op_attivi,
        "sessioni_attive": sessioni_attive,
        "log_recente": log_recente,
    }

@app.post("/api/sessioni/reset")
def reset_sessioni(db=Depends(get_db)):
    """Chiude tutte le sessioni in corso — utile per reset demo."""
    db_execute(db,
        "UPDATE sessioni SET esito='interrotta', fine=datetime('now') WHERE esito='in_corso'"
    )
    db.commit()
    return {"ok": True}

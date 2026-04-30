"""
OMS Industries — Sistema Assemblaggio EMAX2
Backend FastAPI — VERSIONE CLOUD Railway (SQLite)
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

DB_PATH = Path("oms_assemblaggio.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    schema_path = Path("schema.sql")
    if not DB_PATH.exists() and schema_path.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        conn.close()
        print("Database inizializzato.")
    else:
        print(f"Database: {DB_PATH}")

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="OMS Industries — Assemblaggio EMAX2", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/operatori")
def lista_operatori(db: sqlite3.Connection = Depends(get_db)):
    return rows_to_list(db.execute(
        "SELECT id, nome, cognome, ruolo, attivo FROM operatori WHERE attivo=1 ORDER BY cognome"
    ).fetchall())

@app.post("/api/login")
def login(req: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    op = row_to_dict(db.execute("SELECT * FROM operatori WHERE id=? AND attivo=1", (req.operatore_id,)).fetchone())
    if not op: raise HTTPException(401, "Operatore non trovato.")
    if op["pin_hash"] != hash_pin(req.pin): raise HTTPException(401, "PIN non corretto.")
    return {"ok": True, "operatore_id": op["id"], "nome": op["nome"], "cognome": op["cognome"], "ruolo": op["ruolo"]}

@app.get("/api/cicli")
def lista_cicli(db: sqlite3.Connection = Depends(get_db)):
    return rows_to_list(db.execute("SELECT id, codice, nome, descrizione FROM cicli WHERE attivo=1").fetchall())

@app.get("/api/ciclo/{ciclo_id}/step")
def step_ciclo(ciclo_id: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, ordine, titolo, istruzione, tipo_avanzamento, codice_atteso, coppia_min_nm, coppia_max_nm, n_avvitature FROM step WHERE ciclo_id=? ORDER BY ordine", (ciclo_id,)
    ).fetchall()
    if not rows: raise HTTPException(404, "Ciclo non trovato.")
    result = rows_to_list(rows)
    for r in result:
        if r["tipo_avanzamento"] == "avvitatore":
            r["tipo_avanzamento"] = "visivo"
            extra = ""
            if r["coppia_min_nm"] and r["coppia_max_nm"]:
                extra = f" Coppia target: {r['coppia_min_nm']}\u2013{r['coppia_max_nm']} Nm."
            if r["n_avvitature"]:
                extra += f" Esegui {r['n_avvitature']} avvitature."
            r["istruzione"] = r["istruzione"] + extra + " Conferma quando completato."
    return result

@app.post("/api/sessione/avvia", status_code=201)
def avvia_sessione(req: AvviaSessioneRequest, db: sqlite3.Connection = Depends(get_db)):
    in_corso = db.execute("SELECT id FROM sessioni WHERE operatore_id=? AND esito='in_corso'", (req.operatore_id,)).fetchone()
    if in_corso: raise HTTPException(409, f"Sessione già in corso (ID: {in_corso['id']}).")
    cur = db.execute("INSERT INTO sessioni (operatore_id, ciclo_id) VALUES (?,?)", (req.operatore_id, req.ciclo_id))
    db.commit()
    return {"sessione_id": cur.lastrowid, "ok": True}

@app.post("/api/sessione/{sessione_id}/step")
def completa_step(sessione_id: int, req: CompletaStepRequest, db: sqlite3.Connection = Depends(get_db)):
    if not db.execute("SELECT * FROM sessioni WHERE id=? AND esito='in_corso'", (sessione_id,)).fetchone():
        raise HTTPException(404, "Sessione non trovata.")
    cur = db.execute("INSERT INTO log_step (sessione_id, step_id, esito, valore_letto, note) VALUES (?,?,?,?,?)",
        (sessione_id, req.step_id, req.esito, req.valore_letto, req.note))
    db.commit()
    return {"log_step_id": cur.lastrowid, "ok": True}

@app.get("/api/sessione/{sessione_id}")
def stato_sessione(sessione_id: int, db: sqlite3.Connection = Depends(get_db)):
    sessione = row_to_dict(db.execute(
        "SELECT s.*, o.nome, o.cognome, c.codice as ciclo_codice, c.nome as ciclo_nome FROM sessioni s JOIN operatori o ON o.id=s.operatore_id JOIN cicli c ON c.id=s.ciclo_id WHERE s.id=?", (sessione_id,)
    ).fetchone())
    if not sessione: raise HTTPException(404, "Sessione non trovata.")
    completati = rows_to_list(db.execute(
        "SELECT ls.step_id, ls.esito, ls.eseguito_il, st.ordine, st.titolo FROM log_step ls JOIN step st ON st.id=ls.step_id WHERE ls.sessione_id=? ORDER BY ls.eseguito_il", (sessione_id,)
    ).fetchall())
    sessione["step_completati"] = completati
    sessione["n_step_completati"] = len(completati)
    return sessione

@app.post("/api/sessione/{sessione_id}/chiudi")
def chiudi_sessione(sessione_id: int, db: sqlite3.Connection = Depends(get_db)):
    if not db.execute("SELECT * FROM sessioni WHERE id=? AND esito='in_corso'", (sessione_id,)).fetchone():
        raise HTTPException(404, "Sessione non trovata.")
    n_nok = db.execute("SELECT COUNT(*) as n FROM log_step WHERE sessione_id=? AND esito='nok'", (sessione_id,)).fetchone()["n"]
    esito = "completata" if n_nok == 0 else "errore"
    db.execute("UPDATE sessioni SET fine=datetime('now'), esito=? WHERE id=?", (esito, sessione_id))
    db.commit()
    return {"ok": True, "esito": esito}

@app.get("/api/dashboard")
def dashboard(data: Optional[str] = None, db: sqlite3.Connection = Depends(get_db)):
    if not data: data = datetime.now().strftime("%Y-%m-%d")
    cicli = db.execute("SELECT COUNT(*) as n FROM sessioni WHERE esito='completata' AND DATE(fine)=?", (data,)).fetchone()["n"]
    op_attivi = db.execute("SELECT COUNT(DISTINCT operatore_id) as n FROM sessioni WHERE esito='in_corso'").fetchone()["n"]
    log = rows_to_list(db.execute(
        "SELECT ls.eseguito_il, ls.esito, o.nome, o.cognome, st.titolo, st.ordine FROM log_step ls JOIN sessioni s ON s.id=ls.sessione_id JOIN operatori o ON o.id=s.operatore_id JOIN step st ON st.id=ls.step_id WHERE DATE(ls.eseguito_il)=? ORDER BY ls.eseguito_il DESC LIMIT 50", (data,)
    ).fetchall())
    return {"data": data, "cicli_completati": cicli, "operatori_attivi": op_attivi, "log_recente": log}

@app.post("/api/sessioni/reset")
def reset_sessioni(db: sqlite3.Connection = Depends(get_db)):
    db.execute("UPDATE sessioni SET esito='interrotta', fine=datetime('now') WHERE esito='in_corso'")
    db.commit()
    return {"ok": True}

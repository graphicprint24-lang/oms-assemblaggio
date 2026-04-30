PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS operatori (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    cognome     TEXT    NOT NULL,
    pin_hash    TEXT    NOT NULL,
    ruolo       TEXT    NOT NULL DEFAULT 'operatore',
    attivo      INTEGER NOT NULL DEFAULT 1,
    creato_il   TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO operatori (nome, cognome, pin_hash, ruolo) VALUES ('Admin','OMS','9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0','admin');
INSERT INTO operatori (nome, cognome, pin_hash, ruolo) VALUES ('Mario','Rossi','03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4','operatore');
INSERT INTO operatori (nome, cognome, pin_hash, ruolo) VALUES ('Lucia','Ferretti','03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4','operatore');

CREATE TABLE IF NOT EXISTS cicli (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codice      TEXT    NOT NULL UNIQUE,
    nome        TEXT    NOT NULL,
    descrizione TEXT,
    attivo      INTEGER NOT NULL DEFAULT 1
);

INSERT INTO cicli (codice, nome, descrizione) VALUES ('EMAX2','Assemblaggio EMAX2','Ciclo assemblaggio scatola EMAX2');

CREATE TABLE IF NOT EXISTS step (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo_id            INTEGER NOT NULL,
    ordine              INTEGER NOT NULL,
    titolo              TEXT    NOT NULL,
    istruzione          TEXT    NOT NULL,
    tipo_avanzamento    TEXT    NOT NULL,
    codice_atteso       TEXT,
    coppia_min_nm       REAL,
    coppia_max_nm       REAL,
    n_avvitature        INTEGER
);

INSERT INTO step (ciclo_id,ordine,titolo,istruzione,tipo_avanzamento,coppia_min_nm,coppia_max_nm,n_avvitature) VALUES
(1,1,'Prelievo terminali','Preleva i terminali dal magazzino e confermane il codice.','visivo',NULL,NULL,NULL),
(1,2,'Verifica visiva terminali','Verifica i terminali sulla dima. Conferma quando corretto.','visivo',NULL,NULL,NULL),
(1,3,'Prelievo scatola','Preleva la scatola dal magazzino e confermane il codice.','visivo',NULL,NULL,NULL),
(1,4,'Verifica visiva scatola','Verifica la scatola sulla dima. Conferma quando corretto.','visivo',NULL,NULL,NULL),
(1,5,'Prelievo viti','Preleva 24 viti dal magazzino.','visivo',NULL,NULL,NULL),
(1,6,'Serraggio terminali su scatola','Avvita i terminali sulla scatola. Coppia target 8.6 Nm. Esegui 6 avvitature e conferma.','visivo',8.0,9.2,6),
(1,7,'Prelievo grasso lubrificante','Preleva il barattolo di grasso dal magazzino.','visivo',NULL,NULL,NULL),
(1,8,'Lubrificazione terminali','Distribuisci il grasso sulla zona di contatto. Conferma quando completato.','visivo',NULL,NULL,NULL),
(1,9,'Prelievo pinze','Preleva 12 pinze dal magazzino.','visivo',NULL,NULL,NULL),
(1,10,'Inserimento pinze sui terminali','Caletta le pinze sui terminali rispettando il verso. Conferma.','visivo',NULL,NULL,NULL),
(1,11,'Prelievo viti pinze','Preleva 12 viti per pinze dal magazzino.','visivo',NULL,NULL,NULL),
(1,12,'Serraggio pinze su terminali','Avvita le pinze sui terminali. Coppia target 4.0 Nm. Esegui 12 avvitature e conferma.','visivo',3.6,4.4,12),
(1,13,'Fine ciclo — scarico carrello','Sposta il semilavorato sul carrello buffer.','visivo',NULL,NULL,NULL);

CREATE TABLE IF NOT EXISTS sessioni (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operatore_id    INTEGER NOT NULL,
    ciclo_id        INTEGER NOT NULL,
    inizio          TEXT    NOT NULL DEFAULT (datetime('now')),
    fine            TEXT,
    esito           TEXT    DEFAULT 'in_corso'
);

CREATE TABLE IF NOT EXISTS log_step (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sessione_id     INTEGER NOT NULL,
    step_id         INTEGER NOT NULL,
    eseguito_il     TEXT    NOT NULL DEFAULT (datetime('now')),
    esito           TEXT    NOT NULL,
    valore_letto    TEXT,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessioni_operatore ON sessioni(operatore_id);
CREATE INDEX IF NOT EXISTS idx_log_step_sessione  ON log_step(sessione_id);

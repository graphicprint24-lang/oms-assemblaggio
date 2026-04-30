-- ============================================================
-- OMS Industries — Sistema Assemblaggio EMAX2
-- Schema compatibile PostgreSQL e SQLite
-- Versione Cloud 1.0
-- ============================================================

CREATE TABLE IF NOT EXISTS operatori (
    id          SERIAL PRIMARY KEY,
    nome        TEXT    NOT NULL,
    cognome     TEXT    NOT NULL,
    pin_hash    TEXT    NOT NULL,
    ruolo       TEXT    NOT NULL DEFAULT 'operatore'
                        CHECK (ruolo IN ('operatore', 'supervisore', 'admin')),
    attivo      INTEGER NOT NULL DEFAULT 1,
    creato_il   TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO operatori (nome, cognome, pin_hash, ruolo)
VALUES (
    'Admin', 'OMS',
    '9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0',
    'admin'
) ON CONFLICT DO NOTHING;

INSERT INTO operatori (nome, cognome, pin_hash, ruolo)
VALUES (
    'Mario', 'Rossi',
    '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4',
    'operatore'
) ON CONFLICT DO NOTHING;

INSERT INTO operatori (nome, cognome, pin_hash, ruolo)
VALUES (
    'Lucia', 'Ferretti',
    '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4',
    'operatore'
) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS cicli (
    id          SERIAL PRIMARY KEY,
    codice      TEXT    NOT NULL UNIQUE,
    nome        TEXT    NOT NULL,
    descrizione TEXT,
    attivo      INTEGER NOT NULL DEFAULT 1,
    creato_il   TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO cicli (codice, nome, descrizione)
VALUES ('EMAX2', 'Assemblaggio EMAX2', 'Ciclo assemblaggio scatola EMAX2 — fase 1')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS step (
    id                  SERIAL PRIMARY KEY,
    ciclo_id            INTEGER NOT NULL REFERENCES cicli(id) ON DELETE CASCADE,
    ordine              INTEGER NOT NULL,
    titolo              TEXT    NOT NULL,
    istruzione          TEXT    NOT NULL,
    tipo_avanzamento    TEXT    NOT NULL
                        CHECK (tipo_avanzamento IN ('barcode', 'visivo', 'avvitatore')),
    codice_atteso       TEXT,
    coppia_min_nm       NUMERIC,
    coppia_max_nm       NUMERIC,
    n_avvitature        INTEGER,
    UNIQUE (ciclo_id, ordine)
);

INSERT INTO step (ciclo_id, ordine, titolo, istruzione, tipo_avanzamento, codice_atteso, coppia_min_nm, coppia_max_nm, n_avvitature) VALUES
(1, 1,  'Prelievo terminali', 'Preleva fisicamente i terminali dal magazzino postazione e confermane il codice.', 'visivo', NULL, NULL, NULL, NULL),
(1, 2,  'Verifica visiva terminali', 'Verifica aspetto visivo dei terminali e posiziona sulla dima. Conferma quando corretto.', 'visivo', NULL, NULL, NULL, NULL),
(1, 3,  'Prelievo scatola', 'Preleva la scatola dal magazzino e confermane il codice.', 'visivo', NULL, NULL, NULL, NULL),
(1, 4,  'Verifica visiva scatola', 'Verifica aspetto visivo della scatola e posiziona sulla dima. Conferma quando corretto.', 'visivo', NULL, NULL, NULL, NULL),
(1, 5,  'Prelievo viti', 'Preleva 24 viti dal magazzino postazione.', 'visivo', NULL, NULL, NULL, NULL),
(1, 6,  'Serraggio terminali su scatola', 'Avvita i terminali sulla scatola con le viti. Coppia target: 8.6 Nm. Esegui 6 avvitature e conferma.', 'visivo', NULL, 8.0, 9.2, 6),
(1, 7,  'Prelievo grasso lubrificante', 'Preleva il barattolo di grasso lubrificante dal magazzino.', 'visivo', NULL, NULL, NULL, NULL),
(1, 8,  'Lubrificazione terminali', 'Con il pennello distribuisci il grasso sulla zona di contatto pinza del terminale. Conferma quando completato.', 'visivo', NULL, NULL, NULL, NULL),
(1, 9,  'Prelievo pinze', 'Preleva 12 pinze dal magazzino postazione.', 'visivo', NULL, NULL, NULL, NULL),
(1, 10, 'Inserimento pinze sui terminali', 'Caletta le pinze sui terminali rispettando il verso indicato. Conferma quando corretto.', 'visivo', NULL, NULL, NULL, NULL),
(1, 11, 'Prelievo viti pinze', 'Preleva 12 viti per pinze dal magazzino.', 'visivo', NULL, NULL, NULL, NULL),
(1, 12, 'Serraggio pinze su terminali', 'Avvita le pinze sui terminali. Coppia target: 4.0 Nm. Esegui 12 avvitature e conferma.', 'visivo', NULL, 3.6, 4.4, 12),
(1, 13, 'Fine ciclo — scarico carrello', 'Sposta il semilavorato sul carrello buffer destinato alla fase successiva.', 'visivo', NULL, NULL, NULL, NULL)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sessioni (
    id              SERIAL PRIMARY KEY,
    operatore_id    INTEGER NOT NULL REFERENCES operatori(id),
    ciclo_id        INTEGER NOT NULL REFERENCES cicli(id),
    inizio          TIMESTAMP NOT NULL DEFAULT NOW(),
    fine            TIMESTAMP,
    esito           TEXT DEFAULT 'in_corso'
                    CHECK (esito IN ('in_corso', 'completata', 'interrotta', 'errore'))
);

CREATE TABLE IF NOT EXISTS log_step (
    id              SERIAL PRIMARY KEY,
    sessione_id     INTEGER NOT NULL REFERENCES sessioni(id) ON DELETE CASCADE,
    step_id         INTEGER NOT NULL REFERENCES step(id),
    eseguito_il     TIMESTAMP NOT NULL DEFAULT NOW(),
    esito           TEXT NOT NULL CHECK (esito IN ('ok', 'nok', 'saltato')),
    valore_letto    TEXT,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessioni_operatore ON sessioni(operatore_id);
CREATE INDEX IF NOT EXISTS idx_log_step_sessione  ON log_step(sessione_id);

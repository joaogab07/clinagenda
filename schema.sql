-- ClinAgenda - esquema do banco de dados (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    login       TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL CHECK (perfil IN ('admin', 'recepcao'))
);

CREATE TABLE IF NOT EXISTS especialidade (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    descricao   TEXT
);

CREATE TABLE IF NOT EXISTS profissional (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT    NOT NULL,
    registro          TEXT    NOT NULL UNIQUE,   -- CRM, CRO, CRP etc.
    telefone          TEXT,
    email             TEXT,
    ativo             INTEGER NOT NULL DEFAULT 1,
    especialidade_id  INTEGER NOT NULL
        REFERENCES especialidade (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS paciente (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT    NOT NULL,
    cpf              TEXT    NOT NULL UNIQUE,
    data_nascimento  TEXT    NOT NULL,           -- AAAA-MM-DD
    telefone         TEXT    NOT NULL,
    email            TEXT,
    endereco         TEXT
);

CREATE TABLE IF NOT EXISTS consulta (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id      INTEGER NOT NULL REFERENCES paciente (id)     ON DELETE RESTRICT,
    profissional_id  INTEGER NOT NULL REFERENCES profissional (id) ON DELETE RESTRICT,
    usuario_id       INTEGER NOT NULL REFERENCES usuario (id)      ON DELETE RESTRICT,
    data_hora        TEXT    NOT NULL,           -- AAAA-MM-DDTHH:MM
    duracao_min      INTEGER NOT NULL DEFAULT 30 CHECK (duracao_min BETWEEN 10 AND 240),
    status           TEXT    NOT NULL DEFAULT 'agendada'
        CHECK (status IN ('agendada', 'realizada', 'cancelada')),
    observacoes      TEXT,
    criado_em        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_consulta_prof_data ON consulta (profissional_id, data_hora);

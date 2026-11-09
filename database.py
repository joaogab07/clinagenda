"""Acesso ao banco SQLite: conexão por requisição, criação do esquema e dados iniciais."""
import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = Path(__file__).with_name("schema.sql")


def get_db():
    """Abre (uma vez por requisição) a conexão com o banco."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(seed=True):
    """Cria as tabelas e, se o banco estiver vazio, insere o administrador e exemplos."""
    db = get_db()
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    if seed and db.execute("SELECT COUNT(*) FROM usuario").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO usuario (nome, login, senha_hash, perfil) VALUES (?, ?, ?, ?)",
            [
                ("Administrador", "admin", generate_password_hash("admin123"), "admin"),
                ("Recepção", "recepcao", generate_password_hash("recepcao123"), "recepcao"),
            ],
        )
        db.executemany(
            "INSERT INTO especialidade (nome, descricao) VALUES (?, ?)",
            [
                ("Clínica Geral", "Atendimento clínico geral"),
                ("Pediatria", "Atendimento a crianças e adolescentes"),
                ("Odontologia", "Saúde bucal"),
            ],
        )
        db.executemany(
            "INSERT INTO profissional (nome, registro, telefone, email, especialidade_id)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                ("Dra. Ana Souza", "CRM-PR 12345", "(43) 99999-0001", "ana@clinagenda.com", 1),
                ("Dr. Bruno Lima", "CRM-PR 54321", "(43) 99999-0002", "bruno@clinagenda.com", 2),
                ("Dra. Carla Mendes", "CRO-PR 11111", "(43) 99999-0003", "carla@clinagenda.com", 3),
            ],
        )
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command():
        """flask --app app init-db"""
        init_db()
        print("Banco de dados inicializado.")

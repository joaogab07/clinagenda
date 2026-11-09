"""ClinAgenda - sistema de agendamento de consultas para clínicas.

Executar:  python app.py   (cria o banco na primeira vez e sobe em http://127.0.0.1:5000)
"""
import os
import secrets
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

import database
from database import get_db
from models import (Consulta, Especialidade, Paciente, Profissional, Usuario,
                    formatar_cpf, somente_digitos)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao"),
        DATABASE=os.path.join(app.root_path, "clinagenda.db"),
    )
    if config:
        app.config.update(config)
    database.init_app(app)
    with app.app_context():
        database.init_db()
    registrar_rotas(app)
    return app


# ---------------------------------------------------------------- segurança --
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("login", proximo=request.path))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not g.usuario.is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def form_str(nome):
    return (request.form.get(nome) or "").strip()


def form_int(nome):
    valor = form_str(nome)
    return int(valor) if valor.isdigit() else None


# -------------------------------------------------------------------- rotas --
def registrar_rotas(app):

    @app.before_request
    def carregar_usuario():
        g.usuario = None
        uid = session.get("usuario_id")
        if uid:
            row = get_db().execute("SELECT * FROM usuario WHERE id = ?", (uid,)).fetchone()
            if row:
                g.usuario = Usuario(row["id"], row["nome"], row["login"], row["perfil"])
        # proteção CSRF simples: todo POST precisa trazer o token da sessão
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method == "POST" and not app.config.get("TESTING_SEM_CSRF"):
            if request.form.get("csrf") != session["csrf"]:
                abort(400, "Token CSRF inválido.")

    @app.context_processor
    def contexto():
        return {"csrf": session.get("csrf", ""), "formatar_cpf": formatar_cpf}

    @app.template_filter("dt")
    def filtro_data_hora(valor):
        if not valor:
            return ""
        d, _, h = valor.partition("T")
        a, m, dia = d.split("-")
        return f"{dia}/{m}/{a}" + (f" {h[:5]}" if h else "")

    @app.errorhandler(403)
    def proibido(_e):
        return render_template("erro.html", codigo=403,
                               msg="Você não tem permissão para acessar esta página."), 403

    @app.errorhandler(404)
    def nao_encontrado(_e):
        return render_template("erro.html", codigo=404, msg="Registro não encontrado."), 404

    # ------------------------------------------------------- UC01 Autenticar --
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            row = get_db().execute("SELECT * FROM usuario WHERE login = ?",
                                   (form_str("login"),)).fetchone()
            if row and check_password_hash(row["senha_hash"], request.form.get("senha", "")):
                session.clear()
                session["usuario_id"] = row["id"]
                proximo = request.args.get("proximo", "")
                return redirect(proximo if proximo.startswith("/") else url_for("inicio"))
            flash("Login ou senha incorretos.", "erro")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def inicio():
        db = get_db()
        hoje = date.today().isoformat()
        consultas = db.execute(SQL_CONSULTAS + " WHERE date(c.data_hora) = ? "
                               "ORDER BY c.data_hora", (hoje,)).fetchall()
        totais = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("paciente", "profissional", "consulta")}
        return render_template("inicio.html", consultas=consultas, totais=totais)

    # ------------------------------------------------- UC02 Manter pacientes --
    @app.route("/pacientes")
    @login_required
    def pacientes():
        busca = request.args.get("q", "").strip()
        sql, params = "SELECT * FROM paciente", ()
        if busca:
            sql += " WHERE nome LIKE ? OR cpf LIKE ?"
            params = (f"%{busca}%", f"%{somente_digitos(busca) or busca}%")
        rows = get_db().execute(sql + " ORDER BY nome", params).fetchall()
        return render_template("pacientes/lista.html", pacientes=rows, busca=busca)

    @app.route("/pacientes/novo", methods=["GET", "POST"])
    @app.route("/pacientes/<int:id>/editar", methods=["GET", "POST"])
    @login_required
    def paciente_form(id=None):
        db = get_db()
        row = None
        if id:
            row = db.execute("SELECT * FROM paciente WHERE id = ?", (id,)).fetchone() or abort(404)
        if request.method == "POST":
            p = Paciente(id, form_str("nome"), somente_digitos(form_str("cpf")),
                         form_str("data_nascimento"), form_str("telefone"),
                         form_str("email"), form_str("endereco"))
            erros = p.validar()
            if not erros:
                try:
                    if id:
                        db.execute("UPDATE paciente SET nome=?, cpf=?, data_nascimento=?, "
                                   "telefone=?, email=?, endereco=? WHERE id=?",
                                   (p.nome, p.cpf, p.data_nascimento, p.telefone,
                                    p.email, p.endereco, id))
                    else:
                        db.execute("INSERT INTO paciente (nome, cpf, data_nascimento, "
                                   "telefone, email, endereco) VALUES (?, ?, ?, ?, ?, ?)",
                                   (p.nome, p.cpf, p.data_nascimento, p.telefone,
                                    p.email, p.endereco))
                    db.commit()
                    flash("Paciente salvo com sucesso.", "ok")
                    return redirect(url_for("pacientes"))
                except sqlite3.IntegrityError:
                    erros.append("Já existe um paciente com este CPF.")
            for e in erros:
                flash(e, "erro")
            row = request.form
        return render_template("pacientes/form.html", p=row, id=id)

    @app.route("/pacientes/<int:id>/excluir", methods=["POST"])
    @login_required
    def paciente_excluir(id):
        excluir_registro("paciente", id, "Paciente possui consultas e não pode ser excluído.")
        return redirect(url_for("pacientes"))

    # --------------------------------------------- UC03 Manter profissionais --
    @app.route("/profissionais")
    @login_required
    def profissionais():
        rows = get_db().execute(
            "SELECT p.*, e.nome AS especialidade FROM profissional p "
            "JOIN especialidade e ON e.id = p.especialidade_id ORDER BY p.nome").fetchall()
        return render_template("profissionais/lista.html", profissionais=rows)

    @app.route("/profissionais/novo", methods=["GET", "POST"])
    @app.route("/profissionais/<int:id>/editar", methods=["GET", "POST"])
    @admin_required
    def profissional_form(id=None):
        db = get_db()
        row = None
        if id:
            row = db.execute("SELECT * FROM profissional WHERE id = ?", (id,)).fetchone() or abort(404)
        if request.method == "POST":
            p = Profissional(id, form_str("nome"), form_str("registro"),
                             form_int("especialidade_id"), form_str("telefone"),
                             form_str("email"), request.form.get("ativo") == "1")
            erros = p.validar()
            if not erros:
                try:
                    dados = (p.nome, p.registro, p.telefone, p.email, int(p.ativo),
                             p.especialidade_id)
                    if id:
                        db.execute("UPDATE profissional SET nome=?, registro=?, telefone=?, "
                                   "email=?, ativo=?, especialidade_id=? WHERE id=?", dados + (id,))
                    else:
                        db.execute("INSERT INTO profissional (nome, registro, telefone, email, "
                                   "ativo, especialidade_id) VALUES (?, ?, ?, ?, ?, ?)", dados)
                    db.commit()
                    flash("Profissional salvo com sucesso.", "ok")
                    return redirect(url_for("profissionais"))
                except sqlite3.IntegrityError:
                    erros.append("Já existe um profissional com este registro.")
            for e in erros:
                flash(e, "erro")
            row = request.form
        especialidades = db.execute("SELECT * FROM especialidade ORDER BY nome").fetchall()
        return render_template("profissionais/form.html", p=row, id=id,
                               especialidades=especialidades)

    @app.route("/profissionais/<int:id>/excluir", methods=["POST"])
    @admin_required
    def profissional_excluir(id):
        excluir_registro("profissional", id,
                         "Profissional possui consultas. Marque-o como inativo em vez de excluir.")
        return redirect(url_for("profissionais"))

    # -------------------------------------------- UC04 Manter especialidades --
    @app.route("/especialidades")
    @admin_required
    def especialidades():
        rows = get_db().execute(
            "SELECT e.*, COUNT(p.id) AS qtd FROM especialidade e "
            "LEFT JOIN profissional p ON p.especialidade_id = e.id "
            "GROUP BY e.id ORDER BY e.nome").fetchall()
        return render_template("especialidades/lista.html", especialidades=rows)

    @app.route("/especialidades/nova", methods=["GET", "POST"])
    @app.route("/especialidades/<int:id>/editar", methods=["GET", "POST"])
    @admin_required
    def especialidade_form(id=None):
        db = get_db()
        row = None
        if id:
            row = db.execute("SELECT * FROM especialidade WHERE id = ?", (id,)).fetchone() or abort(404)
        if request.method == "POST":
            e = Especialidade(id, form_str("nome"), form_str("descricao"))
            erros = e.validar()
            if not erros:
                try:
                    if id:
                        db.execute("UPDATE especialidade SET nome=?, descricao=? WHERE id=?",
                                   (e.nome, e.descricao, id))
                    else:
                        db.execute("INSERT INTO especialidade (nome, descricao) VALUES (?, ?)",
                                   (e.nome, e.descricao))
                    db.commit()
                    flash("Especialidade salva com sucesso.", "ok")
                    return redirect(url_for("especialidades"))
                except sqlite3.IntegrityError:
                    erros.append("Já existe uma especialidade com este nome.")
            for msg in erros:
                flash(msg, "erro")
            row = request.form
        return render_template("especialidades/form.html", e=row, id=id)

    @app.route("/especialidades/<int:id>/excluir", methods=["POST"])
    @admin_required
    def especialidade_excluir(id):
        excluir_registro("especialidade", id,
                         "Há profissionais nesta especialidade; ela não pode ser excluída.")
        return redirect(url_for("especialidades"))

    # ------------------------------------------------ UC05 Agendar consultas --
    @app.route("/consultas")
    @login_required
    def consultas():
        filtros, params = [], []
        data = request.args.get("data", "")
        prof = request.args.get("profissional", "")
        status = request.args.get("status", "")
        if data:
            filtros.append("date(c.data_hora) = ?"); params.append(data)
        if prof.isdigit():
            filtros.append("c.profissional_id = ?"); params.append(int(prof))
        if status:
            filtros.append("c.status = ?"); params.append(status)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        db = get_db()
        rows = db.execute(SQL_CONSULTAS + where + " ORDER BY c.data_hora DESC", params).fetchall()
        profs = db.execute("SELECT id, nome FROM profissional ORDER BY nome").fetchall()
        return render_template("consultas/lista.html", consultas=rows, profissionais=profs,
                               filtro={"data": data, "profissional": prof, "status": status})

    @app.route("/consultas/nova", methods=["GET", "POST"])
    @app.route("/consultas/<int:id>/editar", methods=["GET", "POST"])
    @login_required
    def consulta_form(id=None):
        db = get_db()
        row = None
        if id:
            row = db.execute("SELECT * FROM consulta WHERE id = ?", (id,)).fetchone() or abort(404)
        if request.method == "POST":
            c = Consulta(id, form_int("paciente_id"), form_int("profissional_id"),
                         form_str("data_hora"), form_int("duracao_min") or 30,
                         form_str("status") or "agendada", form_str("observacoes"),
                         g.usuario.id)
            mudou_horario = (not id or row["data_hora"] != c.data_hora
                             or row["profissional_id"] != c.profissional_id)
            erros = c.validar(nova=mudou_horario)
            if not erros and c.status == "agendada":
                conflito = buscar_conflito(c)
                if conflito:
                    erros.append(f"O profissional já tem consulta às "
                                 f"{conflito.inicio:%H:%M} nesse dia (até {conflito.fim:%H:%M}).")
            if not erros:
                dados = (c.paciente_id, c.profissional_id, c.data_hora, c.duracao_min,
                         c.status, c.observacoes)
                if id:
                    db.execute("UPDATE consulta SET paciente_id=?, profissional_id=?, data_hora=?, "
                               "duracao_min=?, status=?, observacoes=? WHERE id=?", dados + (id,))
                else:
                    db.execute("INSERT INTO consulta (paciente_id, profissional_id, data_hora, "
                               "duracao_min, status, observacoes, usuario_id) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?)", dados + (c.usuario_id,))
                db.commit()
                flash("Consulta salva com sucesso.", "ok")
                return redirect(url_for("consultas"))
            for e in erros:
                flash(e, "erro")
            row = request.form
        pacs = db.execute("SELECT id, nome, cpf FROM paciente ORDER BY nome").fetchall()
        profs = db.execute("SELECT p.id, p.nome, e.nome AS especialidade FROM profissional p "
                           "JOIN especialidade e ON e.id = p.especialidade_id "
                           "WHERE p.ativo = 1 ORDER BY p.nome").fetchall()
        return render_template("consultas/form.html", c=row, id=id,
                               pacientes=pacs, profissionais=profs)

    @app.route("/consultas/<int:id>/cancelar", methods=["POST"])
    @login_required
    def consulta_cancelar(id):
        db = get_db()
        if db.execute("UPDATE consulta SET status = 'cancelada' WHERE id = ?", (id,)).rowcount:
            db.commit()
            flash("Consulta cancelada.", "ok")
        return redirect(url_for("consultas"))

    @app.route("/consultas/<int:id>/excluir", methods=["POST"])
    @admin_required
    def consulta_excluir(id):
        excluir_registro("consulta", id, "")
        return redirect(url_for("consultas"))


SQL_CONSULTAS = (
    "SELECT c.*, pa.nome AS paciente, pr.nome AS profissional, e.nome AS especialidade "
    "FROM consulta c "
    "JOIN paciente pa ON pa.id = c.paciente_id "
    "JOIN profissional pr ON pr.id = c.profissional_id "
    "JOIN especialidade e ON e.id = pr.especialidade_id"
)


def buscar_conflito(nova: Consulta):
    """Procura outra consulta agendada do mesmo profissional no mesmo dia que se sobreponha."""
    rows = get_db().execute(
        "SELECT * FROM consulta WHERE profissional_id = ? AND status = 'agendada' "
        "AND date(data_hora) = date(?) AND id IS NOT ?",
        (nova.profissional_id, nova.data_hora, nova.id)).fetchall()
    for r in rows:
        existente = Consulta(r["id"], r["paciente_id"], r["profissional_id"],
                             r["data_hora"], r["duracao_min"], r["status"])
        if nova.conflita_com(existente):
            return existente
    return None


def excluir_registro(tabela, id, msg_bloqueio):
    db = get_db()
    try:
        if db.execute(f"DELETE FROM {tabela} WHERE id = ?", (id,)).rowcount == 0:
            abort(404)
        db.commit()
        flash("Registro excluído.", "ok")
    except sqlite3.IntegrityError:
        db.rollback()
        flash(msg_bloqueio, "erro")


if __name__ == "__main__":
    create_app().run(debug=True)

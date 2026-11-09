"""Testes automatizados do CRUD e das regras de negócio.  Executar:  python -m pytest"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app  # noqa: E402
from models import Consulta, cpf_valido  # noqa: E402

CPF_OK = "529.982.247-25"


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "TESTING_SEM_CSRF": True,
                      "DATABASE": str(tmp_path / "teste.db")})
    return app.test_client()


def entrar(client, login="admin", senha="admin123"):
    return client.post("/login", data={"login": login, "senha": senha}, follow_redirects=True)


def amanha(hora="10:00"):
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d") + "T" + hora


def novo_paciente(client, cpf=CPF_OK):
    return client.post("/pacientes/novo", follow_redirects=True, data={
        "nome": "Maria Teste", "cpf": cpf, "data_nascimento": "1990-05-10",
        "telefone": "(43) 99999-1234", "email": "maria@teste.com", "endereco": "Rua A"})


def test_cpf():
    assert cpf_valido(CPF_OK)
    assert cpf_valido("123.456.789-00")      # qualquer CPF com 11 números é aceito
    assert cpf_valido("12345678900")
    assert not cpf_valido("123.456.789")      # faltando números
    assert not cpf_valido("")


def test_cadastro_de_conta(client):
    dados = {"nome": "Ana Recepção", "login": "ana", "senha": "segredo1", "confirmacao": "segredo1"}
    r = client.post("/cadastro", data=dados, follow_redirects=True)
    texto = r.get_data(as_text=True)
    assert "Conta criada" in texto and "Olá, Ana Recepção" in texto
    client.get("/logout")
    assert "já está em uso" in client.post("/cadastro", data=dados, follow_redirects=True).get_data(as_text=True)
    r = client.post("/cadastro", follow_redirects=True,
                    data=dict(dados, login="ana2", confirmacao="outra"))
    assert "não conferem" in r.get_data(as_text=True)
    # nova conta entra com perfil Recepção (sem acesso à área do admin)
    entrar(client, "ana", "segredo1")
    assert client.get("/especialidades").status_code == 403


def test_conflito_de_horario():
    a = Consulta(1, 1, 1, "2030-01-01T10:00", 30)
    assert a.conflita_com(Consulta(2, 2, 1, "2030-01-01T10:15", 30))
    assert not a.conflita_com(Consulta(3, 2, 1, "2030-01-01T10:30", 30))


def test_login_obrigatorio_e_senha_errada(client):
    assert client.get("/pacientes").status_code == 302
    assert "incorretos" in entrar(client, senha="errada").get_data(as_text=True)
    assert "Olá, Administrador" in entrar(client).get_data(as_text=True)


def test_crud_paciente(client):
    entrar(client)
    assert "Maria Teste" in novo_paciente(client).get_data(as_text=True)
    assert "Já existe" in novo_paciente(client).get_data(as_text=True)      # CPF único
    assert "11 números" in novo_paciente(client, "123").get_data(as_text=True)
    assert "Paciente salvo" in novo_paciente(client, "123.456.789-00").get_data(as_text=True)
    r = client.post("/pacientes/1/editar", follow_redirects=True, data={
        "nome": "Maria Alterada", "cpf": CPF_OK, "data_nascimento": "1990-05-10",
        "telefone": "(43) 99999-1234"})
    assert "Maria Alterada" in r.get_data(as_text=True)
    assert "Maria Alterada" in client.get("/pacientes?q=alter").get_data(as_text=True)
    r = client.post("/pacientes/1/excluir", follow_redirects=True)
    assert "Maria Alterada" not in r.get_data(as_text=True)


def test_crud_especialidade_e_profissional(client):
    entrar(client)
    client.post("/especialidades/nova", data={"nome": "Cardiologia", "descricao": "Coração"})
    assert "Cardiologia" in client.get("/especialidades").get_data(as_text=True)
    r = client.post("/profissionais/novo", follow_redirects=True, data={
        "nome": "Dr. Novo", "registro": "CRM-PR 99999", "especialidade_id": "4", "ativo": "1"})
    assert "Dr. Novo" in r.get_data(as_text=True)
    # especialidade com profissional vinculado não pode ser excluída
    r = client.post("/especialidades/4/excluir", follow_redirects=True)
    assert "não pode ser excluída" in r.get_data(as_text=True)
    client.post("/profissionais/4/excluir")
    r = client.post("/especialidades/4/excluir", follow_redirects=True)
    assert "Registro excluído" in r.get_data(as_text=True)


def test_recepcao_nao_acessa_area_admin(client):
    entrar(client, "recepcao", "recepcao123")
    assert client.get("/especialidades").status_code == 403
    assert client.get("/profissionais/novo").status_code == 403
    assert client.get("/profissionais").status_code == 200


def test_crud_consulta_com_regras(client):
    entrar(client)
    novo_paciente(client)
    dados = {"paciente_id": "1", "profissional_id": "1", "data_hora": amanha("10:00"),
             "duracao_min": "30", "observacoes": "Retorno"}
    r = client.post("/consultas/nova", data=dados, follow_redirects=True)
    assert "Consulta salva" in r.get_data(as_text=True)
    # mesmo profissional, horário sobreposto -> bloqueado
    r = client.post("/consultas/nova", follow_redirects=True,
                    data=dict(dados, data_hora=amanha("10:15")))
    assert "já tem consulta" in r.get_data(as_text=True)
    # horário no passado -> bloqueado
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT10:00")
    r = client.post("/consultas/nova", follow_redirects=True, data=dict(dados, data_hora=ontem))
    assert "passado" in r.get_data(as_text=True)
    # paciente com consulta não pode ser excluído
    r = client.post("/pacientes/1/excluir", follow_redirects=True)
    assert "possui consultas" in r.get_data(as_text=True)
    # cancelar libera o horário
    client.post("/consultas/1/cancelar")
    assert "Cancelada" in client.get("/consultas?status=cancelada").get_data(as_text=True)
    r = client.post("/consultas/nova", follow_redirects=True,
                    data=dict(dados, data_hora=amanha("10:15")))
    assert "Consulta salva" in r.get_data(as_text=True)
    # editar e excluir
    r = client.post("/consultas/2/editar", follow_redirects=True,
                    data=dict(dados, data_hora=amanha("14:00"), status="agendada"))
    assert "Consulta salva" in r.get_data(as_text=True)
    client.post("/consultas/1/excluir")
    assert client.get("/consultas/1/editar").status_code == 404

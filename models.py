"""Entidades do sistema (espelham o Diagrama de Classes) e suas regras de validação."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

STATUS_CONSULTA = ("agendada", "realizada", "cancelada")


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def cpf_valido(cpf: str) -> bool:
    """Aceita o CPF quando ele tem exatamente 11 números (com ou sem pontos e traço)."""
    return len(somente_digitos(cpf)) == 11


def formatar_cpf(cpf: str) -> str:
    n = somente_digitos(cpf)
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}" if len(n) == 11 else cpf


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Usuario:
    id: Optional[int]
    nome: str
    login: str
    perfil: str  # 'admin' ou 'recepcao'

    def is_admin(self) -> bool:
        return self.perfil == "admin"

    @staticmethod
    def validar_cadastro(nome: str, login: str, senha: str, confirmacao: str) -> list:
        """Regras para criar uma conta nova pela tela de cadastro."""
        erros = []
        if len(nome.strip()) < 3:
            erros.append("Informe seu nome completo.")
        if not re.fullmatch(r"[a-zA-Z0-9._]{3,30}", login):
            erros.append("O login deve ter de 3 a 30 caracteres, usando letras, números, ponto ou _.")
        if len(senha) < 6:
            erros.append("A senha deve ter pelo menos 6 caracteres.")
        if senha != confirmacao:
            erros.append("As senhas não conferem.")
        return erros


@dataclass
class Especialidade:
    id: Optional[int]
    nome: str
    descricao: str = ""

    def validar(self) -> list:
        return [] if self.nome.strip() else ["Informe o nome da especialidade."]


@dataclass
class Profissional:
    id: Optional[int]
    nome: str
    registro: str
    especialidade_id: Optional[int]
    telefone: str = ""
    email: str = ""
    ativo: bool = True

    def validar(self) -> list:
        erros = []
        if not self.nome.strip():
            erros.append("Informe o nome do profissional.")
        if not self.registro.strip():
            erros.append("Informe o registro profissional (CRM, CRO...).")
        if not self.especialidade_id:
            erros.append("Selecione a especialidade.")
        if self.email and not EMAIL_RE.match(self.email):
            erros.append("E-mail inválido.")
        return erros


@dataclass
class Paciente:
    id: Optional[int]
    nome: str
    cpf: str
    data_nascimento: str
    telefone: str
    email: str = ""
    endereco: str = ""

    def validar(self) -> list:
        erros = []
        if not self.nome.strip():
            erros.append("Informe o nome do paciente.")
        if not cpf_valido(self.cpf):
            erros.append("O CPF deve ter 11 números.")
        try:
            nasc = date.fromisoformat(self.data_nascimento)
            if nasc > date.today():
                erros.append("A data de nascimento não pode estar no futuro.")
        except ValueError:
            erros.append("Data de nascimento inválida.")
        if len(somente_digitos(self.telefone)) < 10:
            erros.append("Telefone deve ter DDD e número.")
        if self.email and not EMAIL_RE.match(self.email):
            erros.append("E-mail inválido.")
        return erros


@dataclass
class Consulta:
    id: Optional[int]
    paciente_id: Optional[int]
    profissional_id: Optional[int]
    data_hora: str
    duracao_min: int = 30
    status: str = "agendada"
    observacoes: str = ""
    usuario_id: Optional[int] = None

    @property
    def inicio(self) -> datetime:
        return datetime.fromisoformat(self.data_hora)

    @property
    def fim(self) -> datetime:
        return self.inicio + timedelta(minutes=self.duracao_min)

    def conflita_com(self, outra: "Consulta") -> bool:
        """Dois horários se sobrepõem quando um começa antes de o outro terminar."""
        return self.inicio < outra.fim and outra.inicio < self.fim

    def validar(self, nova: bool = True) -> list:
        erros = []
        if not self.paciente_id:
            erros.append("Selecione o paciente.")
        if not self.profissional_id:
            erros.append("Selecione o profissional.")
        try:
            inicio = self.inicio
            if nova and inicio < datetime.now():
                erros.append("Não é possível agendar no passado.")
            if not 7 <= inicio.hour < 20:
                erros.append("A clínica atende das 07h às 20h.")
        except ValueError:
            erros.append("Data e hora inválidas.")
        if not 10 <= int(self.duracao_min) <= 240:
            erros.append("A duração deve ficar entre 10 e 240 minutos.")
        if self.status not in STATUS_CONSULTA:
            erros.append("Status inválido.")
        return erros

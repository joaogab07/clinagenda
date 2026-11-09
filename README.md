# ClinAgenda — Sistema de Agendamento de Consultas

Projeto da disciplina **Projeto de Desenvolvimento de Software I e II** — UniFil.

**Dupla:**
- Joao Gabriel Ferreira Baptista — RA 232072019
- Jorge Maluf Neto — RA 261466541

## Sobre o sistema

O ClinAgenda é uma aplicação web para a recepção de uma clínica organizar pacientes, profissionais, especialidades e a agenda de consultas. O sistema impede que um profissional receba duas consultas no mesmo horário, não deixa agendar no passado e protege registros que ainda estão em uso (por exemplo, um paciente que já tem consultas não pode ser excluído).

Funcionalidades (CRUD completo):

- **Autenticação** com dois perfis: Administrador e Recepção
- **Pacientes**: cadastrar, listar/buscar por nome ou CPF, editar e excluir (com validação de CPF)
- **Profissionais**: cadastrar, listar, editar, inativar e excluir (somente administrador)
- **Especialidades**: cadastrar, listar, editar e excluir (somente administrador)
- **Consultas**: agendar, listar com filtros (data, profissional, status), editar, cancelar e excluir, com verificação de conflito de horário

## Tecnologias

- Python 3.10+
- Flask 3 (rotas, templates Jinja2, sessões)
- SQLite (banco relacional, acessado com o módulo `sqlite3` e SQL puro)
- HTML5 + CSS3
- Pytest (testes automatizados)

## Como executar

```bash
git clone https://github.com/SEU-USUARIO/clinagenda.git
cd clinagenda
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Acesse **http://127.0.0.1:5000**. Na primeira execução o banco `clinagenda.db` é criado automaticamente com usuários e dados de exemplo:

| Perfil        | Login      | Senha         |
|---------------|------------|---------------|
| Administrador | `admin`    | `admin123`    |
| Recepção      | `recepcao` | `recepcao123` |

Para rodar os testes:

```bash
python -m pytest
```

## Estrutura

```
clinagenda/
├── app.py            # rotas Flask (controladores) e regras de acesso
├── models.py         # entidades (Paciente, Profissional, Especialidade, Consulta, Usuario) e validações
├── database.py       # conexão SQLite, criação do esquema e dados iniciais
├── schema.sql        # DDL do banco (tabelas, chaves e restrições)
├── templates/        # telas em Jinja2
├── static/style.css  # estilos
└── tests/            # testes automatizados
```

## Banco de dados

Cinco tabelas relacionadas: `usuario`, `especialidade`, `profissional`, `paciente` e `consulta`. As chaves estrangeiras usam `ON DELETE RESTRICT`, de modo que o banco recusa excluir uma especialidade com profissionais ou um paciente com consultas. O diagrama entidade-relacionamento está na documentação (PDF).

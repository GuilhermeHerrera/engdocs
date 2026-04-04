# EngDocs — Sistema de Gestão de Documentos de Engenharia

Sistema web profissional em **Python (Flask) + MySQL** para gerenciar documentos técnicos de engenharia.

---

## ✅ Funcionalidades

### Autenticação
- Login / Logout com sessão segura (8h)
- Cadastro de usuário com seleção de perfil
- Recuperação de senha por e-mail (token com validade de 2h)

### Usuários (3 perfis)
| Perfil | Pode |
|---|---|
| **Admin** | Tudo: criar, editar, excluir projetos/documentos/usuários |
| **Engenheiro** | Criar e editar projetos e documentos, enviar versões |
| **Cliente** | Apenas visualizar e baixar arquivos |

### Projetos
- Criar, editar, excluir projetos
- Status: ativo / pausado / concluído / cancelado
- Busca por nome + filtro por status

### Documentos
- Upload de arquivos (PDF, DWG, DXF, RVT, IFC, imagens, DOCX, ZIP)
- Nome, tipo, descrição, status
- Controle de versões (v1, v2, v3…) com histórico completo
- Busca por nome + filtro por tipo e status
- Download com nome original do arquivo
- Status: rascunho / em revisão / aprovado / reprovado / arquivado

### Dashboard & Logs
- Estatísticas (projetos ativos, total de docs, aprovados, em revisão)
- Atividade recente (log de todas as ações)

---

## 🚀 Instalação

### 1. Pré-requisitos
- Python 3.10+
- MySQL 8+

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Criar banco de dados
```bash
mysql -u root -p < schema.sql
```

### 4. Configurar `app.py`
Edite as variáveis no topo do arquivo:

```python
# Banco de dados
user='root'
password=''

# SMTP (para recuperação de senha)
SMTP_HOST     = 'smtp.gmail.com'
SMTP_PORT     = 587
SMTP_USER     = 'seuemail@gmail.com'
SMTP_PASSWORD = 'sua_senha_de_app'   # Use "Senha de App" do Google
APP_URL       = 'http://localhost:5001'
```

> **Dica Gmail:** Ative a verificação em 2 etapas e gere uma "Senha de app" em:
> Conta Google → Segurança → Senhas de app

### 5. Rodar
```bash
python app.py
```

Acesse: **http://localhost:5001**

---

## 📁 Estrutura

```
engdocs/
├── app.py                  # Servidor Flask (toda a lógica)
├── schema.sql              # Banco de dados MySQL
├── requirements.txt
├── README.md
├── static/uploads/         # Arquivos enviados
└── templates/
    ├── base.html           # Layout base com nav
    ├── _auth_base.html     # Base para telas de auth
    ├── login.html
    ├── cadastro.html
    ├── recuperar_senha.html
    ├── resetar_senha.html
    ├── dashboard.html
    ├── projetos.html
    ├── form_projeto.html
    ├── ver_projeto.html
    ├── form_documento.html
    ├── ver_documento.html
    ├── admin_usuarios.html
    └── erro.html
```

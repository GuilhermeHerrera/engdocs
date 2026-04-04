CREATE DATABASE IF NOT EXISTS engdocs CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE engdocs;

-- Usuários
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    tipo ENUM('admin','engenheiro','visualizador') NOT NULL DEFAULT 'visualizador',
    ativo TINYINT(1) DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tokens de recuperação de senha
CREATE TABLE IF NOT EXISTS tokens_recuperacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    token VARCHAR(100) UNIQUE NOT NULL,
    expira_em DATETIME NOT NULL,
    usado TINYINT(1) DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tipos de documento
CREATE TABLE IF NOT EXISTS tipos_documento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL
);

INSERT INTO tipos_documento (nome) VALUES
    ('Planta Técnica'),
    ('Memorial Descritivo'),
    ('Laudo'),
    ('Relatório'),
    ('Especificação Técnica'),
    ('ART/RRT'),
    ('Contrato'),
    ('Outro');

-- Projetos
CREATE TABLE IF NOT EXISTS projetos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    status ENUM('ativo','pausado','concluido','cancelado') DEFAULT 'ativo',
    criado_por INT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (criado_por) REFERENCES usuarios(id)
);

-- Documentos
CREATE TABLE IF NOT EXISTS documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    projeto_id INT NOT NULL,
    tipo_id INT NOT NULL,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    status ENUM('rascunho','em_revisao','aprovado','reprovado','arquivado') DEFAULT 'rascunho',
    criado_por INT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE,
    FOREIGN KEY (tipo_id) REFERENCES tipos_documento(id),
    FOREIGN KEY (criado_por) REFERENCES usuarios(id)
);

-- Versões (arquivos)
CREATE TABLE IF NOT EXISTS versoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documento_id INT NOT NULL,
    numero INT NOT NULL DEFAULT 1,
    arquivo VARCHAR(255) NOT NULL,
    nome_original VARCHAR(255) NOT NULL,
    tamanho_bytes BIGINT,
    notas TEXT,
    enviado_por INT NOT NULL,
    enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE,
    FOREIGN KEY (enviado_por) REFERENCES usuarios(id)
);

-- Log de atividades
CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    acao VARCHAR(100) NOT NULL,
    entidade VARCHAR(50),
    entidade_id INT,
    detalhe TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Usuário admin padrão (senha: admin123)
INSERT INTO usuarios (nome, email, senha_hash, tipo) VALUES (
    'Administrador',
    'admin@engdocs.com',
    'pbkdf2:sha256:600000$default$placeholder',
    'admin'
);

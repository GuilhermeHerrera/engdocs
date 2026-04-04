from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_from_directory, abort)
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import os, uuid, secrets, smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-em-producao-' + secrets.token_hex(16))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# ── Config ─────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'dwg', 'dxf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx', 'zip', 'rvt', 'ifc'}
MAX_FILE_MB = 50
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── SMTP — edite aqui ──────────────────────────────────────────────────────────
SMTP_HOST     = 'smtp.gmail.com'
SMTP_PORT     = 587
SMTP_USER     = 'seuemail@gmail.com'   # altere
SMTP_PASSWORD = 'sua_senha_de_app'     # altere (use senha de app do Gmail)
EMAIL_FROM    = 'EngDocs <seuemail@gmail.com>'
APP_URL       = 'http://localhost:5000' # altere em produção

# ── DB ─────────────────────────────────────────────────────────────────────────
import os
import mysql.connector

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE")
    )

def log(acao, entidade=None, entidade_id=None, detalhe=None):
    try:
        db = get_db(); cur = db.cursor()
        cur.execute(
            'INSERT INTO logs (usuario_id, acao, entidade, entidade_id, detalhe) VALUES (%s,%s,%s,%s,%s)',
            (session.get('usuario_id'), acao, entidade, entidade_id, detalhe)
        )
        db.commit(); db.close()
    except Exception:
        pass

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def humanize_bytes(n):
    if not n: return '—'
    for unit in ['B','KB','MB','GB']:
        if n < 1024: return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'

app.jinja_env.globals['humanize_bytes'] = humanize_bytes

# ── Decoradores ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'usuario_id' not in session:
            flash('Faça login para continuar.', 'info')
            return redirect(url_for('login', next=request.path))
        return f(*a, **kw)
    return dec

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def dec(*a, **kw):
            if session.get('tipo') not in roles:
                abort(403)
            return f(*a, **kw)
        return dec
    return decorator

# ── E-mail ─────────────────────────────────────────────────────────────────────
def send_email(to, subject, body_html):
    try:
        msg = MIMEText(body_html, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, to, msg.as_string())
        return True
    except Exception as e:
        app.logger.error(f'Email error: {e}')
        return False

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'usuario_id' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        senha = request.form['senha']
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM usuarios WHERE email=%s AND ativo=1', (email,))
        u = cur.fetchone(); db.close()
        if u and check_password_hash(u['senha_hash'], senha):
            session.permanent = True
            session.update({'usuario_id': u['id'], 'usuario_nome': u['nome'], 'tipo': u['tipo']})
            log('login')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'erro')
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome  = request.form['nome'].strip()
        email = request.form['email'].strip().lower()
        senha = request.form['senha']
        tipo  = request.form.get('tipo', 'visualizador')
        if len(senha) < 6:
            flash('Senha deve ter pelo menos 6 caracteres.', 'erro')
            return render_template('cadastro.html')
        db = get_db(); cur = db.cursor()
        try:
            cur.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, tipo) VALUES (%s,%s,%s,%s)',
                (nome, email, generate_password_hash(senha), tipo)
            )
            db.commit()
            log('cadastro', 'usuario')
            flash('Conta criada! Faça login.', 'sucesso')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Este e-mail já está cadastrado.', 'erro')
        finally:
            db.close()
    return render_template('cadastro.html')

@app.route('/logout')
def logout():
    log('logout')
    session.clear()
    return redirect(url_for('login'))

# ── Recuperação de senha ───────────────────────────────────────────────────────
@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM usuarios WHERE email=%s AND ativo=1', (email,))
        u = cur.fetchone()
        if u:
            token = secrets.token_urlsafe(32)
            expira = datetime.now() + timedelta(hours=2)
            cur2 = db.cursor()
            cur2.execute(
                'INSERT INTO tokens_recuperacao (usuario_id, token, expira_em) VALUES (%s,%s,%s)',
                (u['id'], token, expira)
            )
            db.commit()
            link = f"{APP_URL}{url_for('resetar_senha', token=token)}"
            html = f"""
            <h2>Recuperação de senha — EngDocs</h2>
            <p>Olá, {u['nome']}!</p>
            <p>Clique no link abaixo para redefinir sua senha. O link expira em <strong>2 horas</strong>.</p>
            <p><a href="{link}" style="background:#4f7cff;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none">Redefinir senha</a></p>
            <p>Se não foi você, ignore este e-mail.</p>
            """
            send_email(email, 'Recuperação de senha — EngDocs', html)
        db.close()
        # Sempre mostrar a mesma mensagem (segurança)
        flash('Se o e-mail existir, você receberá as instruções em breve.', 'info')
        return redirect(url_for('login'))
    return render_template('recuperar_senha.html')

@app.route('/resetar-senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT t.*, u.email FROM tokens_recuperacao t
        JOIN usuarios u ON t.usuario_id = u.id
        WHERE t.token=%s AND t.usado=0 AND t.expira_em > NOW()
    ''', (token,))
    row = cur.fetchone()
    if not row:
        db.close()
        flash('Link inválido ou expirado.', 'erro')
        return redirect(url_for('recuperar_senha'))
    if request.method == 'POST':
        nova = request.form['senha']
        if len(nova) < 6:
            flash('Senha deve ter pelo menos 6 caracteres.', 'erro')
            return render_template('resetar_senha.html', token=token)
        cur2 = db.cursor()
        cur2.execute('UPDATE usuarios SET senha_hash=%s WHERE id=%s',
                     (generate_password_hash(nova), row['usuario_id']))
        cur2.execute('UPDATE tokens_recuperacao SET usado=1 WHERE token=%s', (token,))
        db.commit(); db.close()
        flash('Senha alterada! Faça login.', 'sucesso')
        return redirect(url_for('login'))
    db.close()
    return render_template('resetar_senha.html', token=token)

# ── Dashboard ──────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT COUNT(*) AS t FROM projetos WHERE status="ativo"')
    total_projetos = cur.fetchone()['t']
    cur.execute('SELECT COUNT(*) AS t FROM documentos')
    total_docs = cur.fetchone()['t']
    cur.execute('SELECT COUNT(*) AS t FROM documentos WHERE status="aprovado"')
    aprovados = cur.fetchone()['t']
    cur.execute('SELECT COUNT(*) AS t FROM documentos WHERE status="em_revisao"')
    em_revisao = cur.fetchone()['t']

    cur.execute('''
        SELECT p.*, u.nome AS criado_por_nome,
               COUNT(d.id) AS total_docs
        FROM projetos p
        JOIN usuarios u ON p.criado_por = u.id
        LEFT JOIN documentos d ON d.projeto_id = p.id
        GROUP BY p.id ORDER BY p.atualizado_em DESC LIMIT 6
    ''')
    projetos_recentes = cur.fetchall()

    cur.execute('''
        SELECT l.*, u.nome AS usuario_nome
        FROM logs l LEFT JOIN usuarios u ON l.usuario_id = u.id
        ORDER BY l.criado_em DESC LIMIT 10
    ''')
    logs_recentes = cur.fetchall()
    db.close()
    return render_template('dashboard.html',
        total_projetos=total_projetos, total_docs=total_docs,
        aprovados=aprovados, em_revisao=em_revisao,
        projetos_recentes=projetos_recentes, logs_recentes=logs_recentes)

# ── Projetos ───────────────────────────────────────────────────────────────────
@app.route('/projetos')
@login_required
def listar_projetos():
    q      = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    db = get_db(); cur = db.cursor(dictionary=True)
    sql = '''
        SELECT p.*, u.nome AS criado_por_nome, COUNT(d.id) AS total_docs
        FROM projetos p
        JOIN usuarios u ON p.criado_por = u.id
        LEFT JOIN documentos d ON d.projeto_id = p.id
        WHERE 1=1
    '''
    params = []
    if q:
        sql += ' AND p.nome LIKE %s'; params.append(f'%{q}%')
    if status:
        sql += ' AND p.status = %s'; params.append(status)
    sql += ' GROUP BY p.id ORDER BY p.atualizado_em DESC'
    cur.execute(sql, params)
    projetos = cur.fetchall(); db.close()
    return render_template('projetos.html', projetos=projetos, q=q, status=status)

@app.route('/projetos/novo', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'engenheiro')
def novo_projeto():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        desc = request.form.get('descricao', '').strip()
        db = get_db(); cur = db.cursor()
        cur.execute(
            'INSERT INTO projetos (nome, descricao, criado_por) VALUES (%s,%s,%s)',
            (nome, desc, session['usuario_id'])
        )
        pid = cur.lastrowid
        db.commit(); db.close()
        log('criou projeto', 'projeto', pid, nome)
        flash('Projeto criado!', 'sucesso')
        return redirect(url_for('ver_projeto', projeto_id=pid))
    return render_template('form_projeto.html', projeto=None)

@app.route('/projetos/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'engenheiro')
def editar_projeto(pid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM projetos WHERE id=%s', (pid,))
    projeto = cur.fetchone()
    if not projeto: db.close(); abort(404)
    if request.method == 'POST':
        nome   = request.form['nome'].strip()
        desc   = request.form.get('descricao', '').strip()
        status = request.form['status']
        cur2 = db.cursor()
        cur2.execute('UPDATE projetos SET nome=%s, descricao=%s, status=%s WHERE id=%s',
                     (nome, desc, status, pid))
        db.commit(); db.close()
        log('editou projeto', 'projeto', pid, nome)
        flash('Projeto atualizado!', 'sucesso')
        return redirect(url_for('ver_projeto', projeto_id=pid))
    db.close()
    return render_template('form_projeto.html', projeto=projeto)

@app.route('/projetos/<int:pid>/excluir', methods=['POST'])
@login_required
@roles_required('admin')
def excluir_projeto(pid):
    db = get_db(); cur = db.cursor()
    cur.execute('DELETE FROM projetos WHERE id=%s', (pid,))
    db.commit(); db.close()
    log('excluiu projeto', 'projeto', pid)
    flash('Projeto excluído.', 'sucesso')
    return redirect(url_for('listar_projetos'))

@app.route('/projetos/<int:projeto_id>')
@login_required
def ver_projeto(projeto_id):
    q    = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')
    st   = request.args.get('status', '')
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT p.*, u.nome AS criado_por_nome
        FROM projetos p JOIN usuarios u ON p.criado_por = u.id
        WHERE p.id=%s
    ''', (projeto_id,))
    projeto = cur.fetchone()
    if not projeto: db.close(); abort(404)

    sql = '''
        SELECT d.*, t.nome AS tipo_nome, u.nome AS criado_por_nome,
               (SELECT COUNT(*) FROM versoes WHERE documento_id=d.id) AS total_versoes,
               (SELECT enviado_em FROM versoes WHERE documento_id=d.id ORDER BY numero DESC LIMIT 1) AS ultima_versao
        FROM documentos d
        JOIN tipos_documento t ON d.tipo_id=t.id
        JOIN usuarios u ON d.criado_por=u.id
        WHERE d.projeto_id=%s
    '''
    params = [projeto_id]
    if q:   sql += ' AND d.nome LIKE %s'; params.append(f'%{q}%')
    if tipo: sql += ' AND d.tipo_id=%s'; params.append(tipo)
    if st:  sql += ' AND d.status=%s'; params.append(st)
    sql += ' ORDER BY d.atualizado_em DESC'
    cur.execute(sql, params)
    documentos = cur.fetchall()

    cur.execute('SELECT * FROM tipos_documento ORDER BY nome')
    tipos = cur.fetchall()
    db.close()
    return render_template('ver_projeto.html',
        projeto=projeto, documentos=documentos, tipos=tipos, q=q, tipo=tipo, st=st)

# ── Documentos ─────────────────────────────────────────────────────────────────
@app.route('/projetos/<int:projeto_id>/documentos/novo', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'engenheiro')
def novo_documento(projeto_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM tipos_documento ORDER BY nome')
    tipos = cur.fetchall()
    cur.execute('SELECT id, nome FROM projetos WHERE status!="cancelado" ORDER BY nome')
    projetos = cur.fetchall()

    if request.method == 'POST':
        nome      = request.form['nome'].strip()
        tipo_id   = request.form['tipo_id']
        desc      = request.form.get('descricao', '')
        notas_v   = request.form.get('notas_versao', '')
        proj_dest = request.form.get('projeto_id', projeto_id)

        cur2 = db.cursor()
        cur2.execute(
            'INSERT INTO documentos (projeto_id, tipo_id, nome, descricao, criado_por) VALUES (%s,%s,%s,%s,%s)',
            (proj_dest, tipo_id, nome, desc, session['usuario_id'])
        )
        doc_id = cur2.lastrowid

        f = request.files.get('arquivo')
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            fname = f'{uuid.uuid4().hex}.{ext}'
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            f.save(fpath)
            tamanho = os.path.getsize(fpath)
            cur2.execute(
                'INSERT INTO versoes (documento_id, numero, arquivo, nome_original, tamanho_bytes, enviado_por, notas) VALUES (%s,1,%s,%s,%s,%s,%s)',
                (doc_id, fname, secure_filename(f.filename), tamanho, session['usuario_id'], notas_v)
            )
        db.commit(); db.close()
        log('criou documento', 'documento', doc_id, nome)
        flash('Documento criado!', 'sucesso')
        return redirect(url_for('ver_documento', doc_id=doc_id))
    db.close()
    return render_template('form_documento.html',
        projeto_id=projeto_id, tipos=tipos, projetos=projetos, documento=None)

@app.route('/documentos/<int:doc_id>')
@login_required
def ver_documento(doc_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT d.*, t.nome AS tipo_nome, p.nome AS projeto_nome, p.id AS projeto_id,
               u.nome AS criado_por_nome
        FROM documentos d
        JOIN tipos_documento t ON d.tipo_id=t.id
        JOIN projetos p ON d.projeto_id=p.id
        JOIN usuarios u ON d.criado_por=u.id
        WHERE d.id=%s
    ''', (doc_id,))
    doc = cur.fetchone()
    if not doc: db.close(); abort(404)

    cur.execute('''
        SELECT v.*, u.nome AS enviado_por_nome
        FROM versoes v JOIN usuarios u ON v.enviado_por=u.id
        WHERE v.documento_id=%s ORDER BY v.numero DESC
    ''', (doc_id,))
    versoes = cur.fetchall()
    db.close()
    return render_template('ver_documento.html', doc=doc, versoes=versoes)

@app.route('/documentos/<int:doc_id>/editar', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'engenheiro')
def editar_documento(doc_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM documentos WHERE id=%s', (doc_id,))
    doc = cur.fetchone()
    if not doc: db.close(); abort(404)
    cur.execute('SELECT * FROM tipos_documento ORDER BY nome')
    tipos = cur.fetchall()
    cur.execute('SELECT id, nome FROM projetos WHERE status!="cancelado" ORDER BY nome')
    projetos = cur.fetchall()

    if request.method == 'POST':
        nome    = request.form['nome'].strip()
        tipo_id = request.form['tipo_id']
        desc    = request.form.get('descricao', '')
        status  = request.form['status']
        proj_id = request.form.get('projeto_id', doc['projeto_id'])
        cur2 = db.cursor()
        cur2.execute(
            'UPDATE documentos SET nome=%s, tipo_id=%s, descricao=%s, status=%s, projeto_id=%s WHERE id=%s',
            (nome, tipo_id, desc, status, proj_id, doc_id)
        )
        db.commit(); db.close()
        log('editou documento', 'documento', doc_id, nome)
        flash('Documento atualizado!', 'sucesso')
        return redirect(url_for('ver_documento', doc_id=doc_id))
    db.close()
    return render_template('form_documento.html',
        documento=doc, tipos=tipos, projetos=projetos, projeto_id=doc['projeto_id'])

@app.route('/documentos/<int:doc_id>/excluir', methods=['POST'])
@login_required
@roles_required('admin')
def excluir_documento(doc_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT projeto_id FROM documentos WHERE id=%s', (doc_id,))
    row = cur.fetchone()
    pid = row['projeto_id'] if row else None
    cur2 = db.cursor()
    cur2.execute('DELETE FROM documentos WHERE id=%s', (doc_id,))
    db.commit(); db.close()
    log('excluiu documento', 'documento', doc_id)
    flash('Documento excluído.', 'sucesso')
    return redirect(url_for('ver_projeto', projeto_id=pid) if pid else url_for('listar_projetos'))

@app.route('/documentos/<int:doc_id>/nova-versao', methods=['POST'])
@login_required
@roles_required('admin', 'engenheiro')
def nova_versao(doc_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT MAX(numero) AS m FROM versoes WHERE documento_id=%s', (doc_id,))
    prox = (cur.fetchone()['m'] or 0) + 1
    notas = request.form.get('notas', '')
    f = request.files.get('arquivo')
    if f and f.filename and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        fname = f'{uuid.uuid4().hex}.{ext}'
        fpath = os.path.join(UPLOAD_FOLDER, fname)
        f.save(fpath)
        tamanho = os.path.getsize(fpath)
        cur2 = db.cursor()
        cur2.execute(
            'INSERT INTO versoes (documento_id, numero, arquivo, nome_original, tamanho_bytes, enviado_por, notas) VALUES (%s,%s,%s,%s,%s,%s,%s)',
            (doc_id, prox, fname, secure_filename(f.filename), tamanho, session['usuario_id'], notas)
        )
        cur2.execute("UPDATE documentos SET status='em_revisao', atualizado_em=NOW() WHERE id=%s", (doc_id,))
        db.commit()
        log('enviou versão', 'documento', doc_id, f'v{prox}')
        flash(f'Versão {prox} enviada!', 'sucesso')
    else:
        flash('Arquivo inválido.', 'erro')
    db.close()
    return redirect(url_for('ver_documento', doc_id=doc_id))

@app.route('/documentos/<int:doc_id>/status', methods=['POST'])
@login_required
@roles_required('admin', 'engenheiro')
def atualizar_status(doc_id):
    status = request.form['status']
    db = get_db(); cur = db.cursor()
    cur.execute('UPDATE documentos SET status=%s WHERE id=%s', (status, doc_id))
    db.commit(); db.close()
    log('alterou status', 'documento', doc_id, status)
    flash('Status atualizado!', 'sucesso')
    return redirect(url_for('ver_documento', doc_id=doc_id))

# ── Download ───────────────────────────────────────────────────────────────────
@app.route('/download/<filename>')
@login_required
def download(filename):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT nome_original FROM versoes WHERE arquivo=%s', (filename,))
    row = cur.fetchone(); db.close()
    nome_orig = row['nome_original'] if row else filename
    log('download', 'arquivo', None, filename)
    return send_from_directory(UPLOAD_FOLDER, filename,
                               as_attachment=True, download_name=nome_orig)

# ── Admin: usuários ────────────────────────────────────────────────────────────
@app.route('/admin/usuarios')
@login_required
@roles_required('admin')
def admin_usuarios():
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM usuarios ORDER BY criado_em DESC')
    usuarios = cur.fetchall(); db.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/<int:uid>/tipo', methods=['POST'])
@login_required
@roles_required('admin')
def alterar_tipo(uid):
    tipo = request.form['tipo']
    db = get_db(); cur = db.cursor()
    cur.execute('UPDATE usuarios SET tipo=%s WHERE id=%s', (tipo, uid))
    db.commit(); db.close()
    log('alterou tipo usuário', 'usuario', uid, tipo)
    flash('Tipo alterado!', 'sucesso')
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/<int:uid>/toggle', methods=['POST'])
@login_required
@roles_required('admin')
def toggle_usuario(uid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT ativo FROM usuarios WHERE id=%s', (uid,))
    u = cur.fetchone()
    novo = 0 if u['ativo'] else 1
    cur2 = db.cursor()
    cur2.execute('UPDATE usuarios SET ativo=%s WHERE id=%s', (novo, uid))
    db.commit(); db.close()
    log('ativou/desativou usuário', 'usuario', uid)
    flash('Usuário atualizado!', 'sucesso')
    return redirect(url_for('admin_usuarios'))

# ── Erros ──────────────────────────────────────────────────────────────────────
@app.errorhandler(403)
def err403(e): return render_template('erro.html', codigo=403, msg='Acesso negado.'), 403

@app.errorhandler(404)
def err404(e): return render_template('erro.html', codigo=404, msg='Página não encontrada.'), 404

import os

import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)

@app.route("/")
def home():
    return "App funcionando 🚀"


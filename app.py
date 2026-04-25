import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template_string, request, redirect, url_for, session, g

app = Flask(__name__)
# 환경 변수에서 시크릿 키와 DB 주소를 가져옵니다. (없으면 로컬 테스트용 기본값 사용)
app.secret_key = os.environ.get('SECRET_KEY', 'local_secret_key')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/studychosun')

# --- 1. 데이터베이스 연결 및 초기화 ---
def get_db():
    if not hasattr(g, '_database'):
        g._database = psycopg2.connect(DATABASE_URL)
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    # 실제 서버(DATABASE_URL이 설정된 경우)에서만 테이블을 생성하도록 방어 로직 추가
    if 'localhost' in DATABASE_URL:
        return
        
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    # PostgreSQL은 AUTOINCREMENT 대신 SERIAL을 사용합니다.
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE, password TEXT, points INTEGER DEFAULT 100)''')
    c.execute('''CREATE TABLE IF NOT EXISTS qna (
                    id SERIAL PRIMARY KEY,
                    title TEXT, content TEXT, bounty INTEGER, author_id INTEGER, resolved INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS answers (
                    id SERIAL PRIMARY KEY,
                    qna_id INTEGER, content TEXT, author_id INTEGER, accepted INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS materials (
                    id SERIAL PRIMARY KEY,
                    title TEXT, content TEXT, price INTEGER, author_id INTEGER)''')
    
    # 더미 데이터 (중복 삽입 방지를 위해 ON CONFLICT 사용)
    c.execute("INSERT INTO users (username, password, points) VALUES ('admin', '1234', 1000) ON CONFLICT (username) DO NOTHING")
    conn.commit()
    c.close()
    conn.close()

# --- 2. HTML 템플릿 (기존과 동일) ---
BASE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>StudyChosun v1.0</title>
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background: #004b87; color: white; padding: 15px; border-radius: 5px; }
        .nav { margin: 15px 0; padding: 10px; background: #f1f1f1; border-radius: 5px; }
        .nav a { margin-right: 15px; text-decoration: none; color: #333; font-weight: bold; }
        .card { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
        .btn { padding: 8px 15px; background: #004b87; color: white; border: none; border-radius: 3px; cursor: pointer; }
        .btn:hover { background: #003366; }
        .highlight { background-color: #e6f7ff; border-left: 5px solid #004b87; }
    </style>
</head>
<body>
    <div class="header">
        <h1>StudyChosun (실 운영 테스트용)</h1>
    </div>
    <div class="nav">
        <a href="/">홈</a>
        <a href="/qna">Q&A 게시판</a>
        <a href="/materials">자료실</a>
        <span style="float:right;">
        {% if session.user_id %}
            <b>{{ session.username }}</b>님 (현재: {{ points }} P) | <a href="/logout">로그아웃</a>
        {% else %}
            <a href="/login">로그인 및 회원가입</a>
        {% endif %}
        </span>
    </div>
    <div style="color:red; font-weight:bold; margin-bottom:10px;">{{ error }}</div>
    {% block content %}{% endblock %}
</body>
</html>
'''

def render(block_content, **kwargs):
    html = BASE_HTML.replace('{% block content %}{% endblock %}', block_content)
    return render_template_string(html, **kwargs)

@app.context_processor
def inject_points():
    if 'user_id' in session:
        c = get_db().cursor()
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        row = c.fetchone()
        c.close()
        return dict(points=row[0] if row else 0)
    return dict(points=0)

# --- 3. 비즈니스 로직 (SQLite의 ? 를 PostgreSQL의 %s 로 모두 변경) ---

@app.route('/')
def index():
    # 서버 구동 시 DB 테이블 초기화 실행
    init_db()
    return render("<h2>환영합니다!</h2><p>조선대학교 학우들을 위한 지식 공유 플랫폼입니다.</p>")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action, username, password = request.form.get('action'), request.form.get('username'), request.form.get('password')
        db = get_db(); c = db.cursor()
        
        if action == 'register':
            try:
                c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
                db.commit()
                c.close()
                return render("<h2>가입 성공!</h2><p>100P가 지급되었습니다. 이제 로그인해주세요.</p>")
            except psycopg2.IntegrityError:
                db.rollback()
                c.close()
                return render("<h2>로그인/가입</h2>", error="이미 존재하는 아이디입니다.")
        elif action == 'login':
            c.execute("SELECT id, username FROM users WHERE username=%s AND password=%s", (username, password))
            user = c.fetchone()
            c.close()
            if user:
                session['user_id'], session['username'] = user[0], user[1]
                return redirect(url_for('index'))
            return render("<h2>로그인/가입</h2>", error="아이디 또는 비밀번호가 틀렸습니다.")
            
    return render('''
    <h2>로그인 / 회원가입</h2>
    <form method="post" class="card">
        아이디: <input type="text" name="username" required> 
        비밀번호: <input type="password" name="password" required> <br><br>
        <button type="submit" name="action" value="login" class="btn">로그인</button>
        <button type="submit" name="action" value="register" class="btn" style="background:#28a745;">회원가입 (100P 지급)</button>
    </form>
    ''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/qna')
def qna():
    c = get_db().cursor()
    c.execute("SELECT * FROM qna ORDER BY id DESC")
    qs = c.fetchall()
    c.close()
    html = '<h2>Q&A 게시판</h2><a href="/qna/ask" class="btn">질문 작성하기 (포인트 걸기)</a><hr>'
    for q in qs:
        status = "✅ 채택완료" if q[5] else "진행중"
        html += f'<div class="card"><h3><a href="/qna/{q[0]}">{q[1]}</a> <span style="color:red;">[현상금: {q[3]}P]</span></h3><p>{status} | 작성자 ID: {q[4]}</p></div>'
    return render(html)

@app.route('/qna/ask', methods=['GET', 'POST'])
def qna_ask():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        title, content, bounty = request.form['title'], request.form['content'], int(request.form['bounty'])
        db = get_db(); c = db.cursor()
        
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        if c.fetchone()[0] < bounty: 
            c.close()
            return render("", error="포인트가 부족합니다.")
        
        c.execute("UPDATE users SET points = points - %s WHERE id=%s", (bounty, session['user_id']))
        c.execute("INSERT INTO qna (title, content, bounty, author_id) VALUES (%s, %s, %s, %s)", (title, content, bounty, session['user_id']))
        db.commit()
        c.close()
        return redirect(url_for('qna'))
        
    return render('''
    <h2>질문 작성하기</h2>
    <form method="post" class="card">
        제목: <input type="text" name="title" style="width:100%;" required><br><br>
        내용: <textarea name="content" rows="5" style="width:100%;" required></textarea><br><br>
        걸 포인트(P): <input type="number" name="bounty" required min="10"><br><br>
        <button type="submit" class="btn">질문 등록 (포인트 즉시 차감)</button>
    </form>
    ''')

@app.route('/qna/<int:q_id>', methods=['GET', 'POST'])
def qna_detail(q_id):
    db = get_db(); c = db.cursor()
    if request.method == 'POST' and 'user_id' in session:
        c.execute("INSERT INTO answers (qna_id, content, author_id) VALUES (%s, %s, %s)", (q_id, request.form['content'], session['user_id']))
        db.commit()
        c.close()
        return redirect(url_for('qna_detail', q_id=q_id))

    c.execute("SELECT * FROM qna WHERE id=%s", (q_id,)); q = c.fetchone()
    c.execute("SELECT * FROM answers WHERE qna_id=%s", (q_id,)); answers = c.fetchall()
    c.close()
    
    html = f'<h2>{q[1]}</h2><p><b>현상금: {q[3]}P</b></p><div class="card">{q[2]}</div><h3>답변 목록</h3>'
    for a in answers:
        is_accepted = 'highlight' if a[4] else ''
        accept_badge = '<b style="color:#004b87;">★ 채택된 답변입니다 (포인트 획득)</b><br>' if a[4] else ''
        accept_btn = ''
        if 'user_id' in session and session['user_id'] == q[4] and not q[5]:
            accept_btn = f'<form method="post" action="/qna/{q[0]}/accept/{a[0]}"><button class="btn" style="background:#28a745;">이 답변 채택하기</button></form>'
        
        html += f'<div class="card {is_accepted}">{accept_badge}<p>{a[2]}</p>{accept_btn}</div>'

    if 'user_id' in session and session['user_id'] != q[4]:
        html += '<form method="post"><textarea name="content" rows="3" style="width:100%;" required></textarea><br><br><button class="btn">답변 등록</button></form>'
    return render(html)

@app.route('/qna/<int:q_id>/accept/<int:a_id>', methods=['POST'])
def qna_accept(q_id, a_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    c.execute("SELECT author_id, bounty, resolved FROM qna WHERE id=%s", (q_id,)); q = c.fetchone()
    
    if q and q[0] == session['user_id'] and not q[2]:
        c.execute("SELECT author_id FROM answers WHERE id=%s", (a_id,)); a_author = c.fetchone()[0]
        c.execute("UPDATE qna SET resolved=1 WHERE id=%s", (q_id,))
        c.execute("UPDATE answers SET accepted=1 WHERE id=%s", (a_id,))
        c.execute("UPDATE users SET points = points + %s WHERE id=%s", (q[1], a_author))
        db.commit()
    c.close()
    return redirect(url_for('qna_detail', q_id=q_id))

@app.route('/materials')
def materials():
    c = get_db().cursor()
    c.execute("SELECT * FROM materials ORDER BY id DESC"); mats = c.fetchall()
    c.close()
    error = request.args.get('error', '')
    
    html = f'<h2>공부 자료실</h2><a href="/materials/upload" class="btn">자료 업로드 (판매)</a><hr>'
    for m in mats:
        html += f'<div class="card"><h3>{m[1]}</h3><p>가격: <b>{m[3]}P</b></p>'
        html += f'<form method="post" action="/materials/{m[0]}/buy"><button class="btn">포인트 지불하고 내용 보기</button></form></div>'
    return render(html, error=error)

@app.route('/materials/upload', methods=['GET', 'POST'])
def mat_upload():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        db = get_db(); c = db.cursor()
        c.execute("INSERT INTO materials (title, content, price, author_id) VALUES (%s, %s, %s, %s)", 
                   (request.form['title'], request.form['content'], int(request.form['price']), session['user_id']))
        db.commit()
        c.close()
        return redirect(url_for('materials'))
        
    return render('''
    <h2>자료 업로드</h2>
    <form method="post" class="card">
        자료 제목: <input type="text" name="title" style="width:100%;" required><br><br>
        핵심 요약본 내용 (또는 다운로드 링크): <textarea name="content" rows="5" style="width:100%;" required></textarea><br><br>
        판매 가격(P): <input type="number" name="price" required min="0"><br><br>
        <button type="submit" class="btn">자료 등록</button>
    </form>
    ''')

@app.route('/materials/<int:m_id>/buy', methods=['POST'])
def mat_buy(m_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    c.execute("SELECT price, author_id FROM materials WHERE id=%s", (m_id,)); mat = c.fetchone()
    
    c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],)); my_pts = c.fetchone()[0]
    if my_pts < mat[0]: 
        c.close()
        return redirect(url_for('materials', error="포인트가 부족합니다."))
        
    c.execute("UPDATE users SET points = points - %s WHERE id=%s", (mat[0], session['user_id']))
    c.execute("UPDATE users SET points = points + %s WHERE id=%s", (mat[0], mat[1]))
    db.commit()
    c.close()
    
    session[f'bought_{m_id}'] = True
    return redirect(url_for('mat_view', m_id=m_id))

@app.route('/materials/<int:m_id>', methods=['GET'])
def mat_view(m_id):
    if 'user_id' not in session or not session.get(f'bought_{m_id}'):
        return redirect(url_for('materials', error="구매 후 열람 가능합니다."))
    c = get_db().cursor()
    c.execute("SELECT * FROM materials WHERE id=%s", (m_id,)); m = c.fetchone()
    c.close()
    return render(f'<h2>{m[1]}</h2><div class="card"><h4>자료 본문:</h4><pre style="white-space: pre-wrap;">{m[2]}</pre></div><a href="/materials" class="btn">목록으로</a>')

if __name__ == '__main__':
    app.run(debug=True)
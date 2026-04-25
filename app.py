import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, g

app = Flask(__name__)
# 세션 암호화를 위한 시크릿 키
app.secret_key = 'studychosun_v1_secret_key'

# --- 1. 데이터베이스 초기화 및 더미 데이터 ---
def init_db():
    with sqlite3.connect('studychosun.db') as conn:
        c = conn.cursor()
        # 회원 정보 (points 컬럼으로 포인트 관리)
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE, password TEXT, points INTEGER DEFAULT 100)''')
        # QnA 게시판 (bounty: 걸린 현상금, resolved: 채택 여부)
        c.execute('''CREATE TABLE IF NOT EXISTS qna (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT, content TEXT, bounty INTEGER, author_id INTEGER, resolved INTEGER DEFAULT 0)''')
        # QnA 답변 (accepted: 채택된 답변 여부)
        c.execute('''CREATE TABLE IF NOT EXISTS answers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        qna_id INTEGER, content TEXT, author_id INTEGER, accepted INTEGER DEFAULT 0)''')
        # 자료실 (price: 열람 가격)
        c.execute('''CREATE TABLE IF NOT EXISTS materials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT, content TEXT, price INTEGER, author_id INTEGER)''')
        
        # 시연용 더미 데이터 삽입
        c.execute("INSERT OR IGNORE INTO users (username, password, points) VALUES ('admin', '1234', 1000)")
        c.execute("INSERT OR IGNORE INTO qna (title, content, bounty, author_id) VALUES ('소프트웨어 공학 UML 관련 질문', '클래스 다이어그램 작성 시 연관관계가 헷갈립니다.', 50, 1)")
        conn.commit()

# --- 2. HTML 템플릿 레이아웃 ---
# Flask의 Jinja2 엔진이 {{ }} 또는 {% %} 구문을 렌더링하며, 기본적으로 HTML 자동 이스케이프를 지원하여 DOM XSS 공격을 방지합니다.
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
        <h1>StudyChosun (중간발표 시연용 v1.0)</h1>
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

# 템플릿 렌더링 헬퍼 함수
def render(block_content, **kwargs):
    html = BASE_HTML.replace('{% block content %}{% endblock %}', block_content)
    return render_template_string(html, **kwargs)

# DB 연결 헬퍼 함수
def get_db():
    if not hasattr(g, '_database'): g._database = sqlite3.connect('studychosun.db')
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, '_database'): g._database.close()

# 모든 페이지에 현재 포인트 전달
@app.context_processor
def inject_points():
    if 'user_id' in session:
        c = get_db().cursor()
        c.execute("SELECT points FROM users WHERE id=?", (session['user_id'],))
        row = c.fetchone()
        return dict(points=row[0] if row else 0)
    return dict(points=0)

# --- 3. 라우팅 (비즈니스 로직) ---

@app.route('/')
def index():
    return render("<h2>환영합니다!</h2><p>조선대학교 학우들을 위한 지식 공유 플랫폼입니다.</p><p>위 메뉴를 클릭하여 기능을 확인해보세요.</p>")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action, username, password = request.form.get('action'), request.form.get('username'), request.form.get('password')
        db = get_db(); c = db.cursor()
        
        if action == 'register':
            try:
                # 가입 시 기본 포인트 100 지급
                c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                db.commit()
                return render("<h2>가입 성공!</h2><p>100P가 지급되었습니다. 이제 로그인해주세요.</p>")
            except sqlite3.IntegrityError:
                return render("<h2>로그인/가입</h2>", error="이미 존재하는 아이디입니다.")
        elif action == 'login':
            c.execute("SELECT id, username FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
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
        
        c.execute("SELECT points FROM users WHERE id=?", (session['user_id'],))
        if c.fetchone()[0] < bounty: return render("", error="포인트가 부족합니다.")
        
        # 포인트 차감 및 질문 등록 (DB 트랜잭션)
        c.execute("UPDATE users SET points = points - ? WHERE id=?", (bounty, session['user_id']))
        c.execute("INSERT INTO qna (title, content, bounty, author_id) VALUES (?, ?, ?, ?)", (title, content, bounty, session['user_id']))
        db.commit()
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
        c.execute("INSERT INTO answers (qna_id, content, author_id) VALUES (?, ?, ?)", (q_id, request.form['content'], session['user_id']))
        db.commit()
        return redirect(url_for('qna_detail', q_id=q_id))

    c.execute("SELECT * FROM qna WHERE id=?", (q_id,)); q = c.fetchone()
    c.execute("SELECT * FROM answers WHERE qna_id=?", (q_id,)); answers = c.fetchall()
    
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
    c.execute("SELECT author_id, bounty, resolved FROM qna WHERE id=?", (q_id,)); q = c.fetchone()
    
    # 본인 질문이고 아직 채택되지 않았을 때만 로직 실행
    if q and q[0] == session['user_id'] and not q[2]:
        c.execute("SELECT author_id FROM answers WHERE id=?", (a_id,)); a_author = c.fetchone()[0]
        c.execute("UPDATE qna SET resolved=1 WHERE id=?", (q_id,))
        c.execute("UPDATE answers SET accepted=1 WHERE id=?", (a_id,))
        # 답변자에게 포인트 지급
        c.execute("UPDATE users SET points = points + ? WHERE id=?", (q[1], a_author))
        db.commit()
    return redirect(url_for('qna_detail', q_id=q_id))

@app.route('/materials')
def materials():
    c = get_db().cursor()
    c.execute("SELECT * FROM materials ORDER BY id DESC"); mats = c.fetchall()
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
        db = get_db()
        db.execute("INSERT INTO materials (title, content, price, author_id) VALUES (?, ?, ?, ?)", 
                   (request.form['title'], request.form['content'], int(request.form['price']), session['user_id']))
        db.commit()
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
    c.execute("SELECT price, author_id FROM materials WHERE id=?", (m_id,)); mat = c.fetchone()
    
    c.execute("SELECT points FROM users WHERE id=?", (session['user_id'],)); my_pts = c.fetchone()[0]
    if my_pts < mat[0]: return redirect(url_for('materials', error="포인트가 부족합니다."))
        
    # 구매자 포인트 차감, 판매자 포인트 증가
    c.execute("UPDATE users SET points = points - ? WHERE id=?", (mat[0], session['user_id']))
    c.execute("UPDATE users SET points = points + ? WHERE id=?", (mat[0], mat[1]))
    db.commit()
    
    session[f'bought_{m_id}'] = True
    return redirect(url_for('mat_view', m_id=m_id))

@app.route('/materials/<int:m_id>', methods=['GET'])
def mat_view(m_id):
    if 'user_id' not in session or not session.get(f'bought_{m_id}'):
        return redirect(url_for('materials', error="구매 후 열람 가능합니다."))
    c = get_db().cursor()
    c.execute("SELECT * FROM materials WHERE id=?", (m_id,)); m = c.fetchone()
    return render(f'<h2>{m[1]}</h2><div class="card"><h4>자료 본문:</h4><pre style="white-space: pre-wrap;">{m[2]}</pre></div><a href="/materials" class="btn">목록으로</a>')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
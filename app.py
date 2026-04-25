import os
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template_string, request, redirect, url_for, session, g, flash
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chosun_secure_v2')
DATABASE_URL = os.environ.get('DATABASE_URL')

# Cloudinary 설정
cloudinary.config(cloudinary_url=os.environ.get('CLOUDINARY_URL'))

# 과목 리스트 정의
SUBJECTS = {
    'computer_networks': '컴퓨터네트워크',
    'deep_learning': '딥러닝기초',
    'software_engineering': '소프트웨어공학',
    'fullstack': '풀스택개발및응용',
    'security': '인터넷보안'
}

# --- DB 연결 함수 ---
def get_db():
    if not hasattr(g, '_database'):
        g._database = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

# --- 포인트 인젝터 (네비게이션 바 표시용) ---
@app.context_processor
def inject_user_info():
    if 'user_id' in session:
        db = get_db(); c = db.cursor()
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        row = c.fetchone()
        return dict(points=row['points'] if row else 0, SUBJECTS=SUBJECTS)
    return dict(points=0, SUBJECTS=SUBJECTS)

# --- 공통 레이아웃 ---
BASE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>StudyChosun v2.0</title>
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f9f9f9; }
        .header { background: #004b87; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
        .nav { background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .nav a { margin-right: 15px; text-decoration: none; color: #333; font-weight: bold; }
        .subject-card { display: inline-block; width: 30%; background: white; padding: 20px; margin: 1.5%; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; cursor: pointer; transition: 0.3s; }
        .subject-card:hover { transform: translateY(-5px); border: 2px solid #004b87; }
        .card { background: white; border: 1px solid #ddd; padding: 20px; margin-bottom: 15px; border-radius: 8px; }
        .btn { padding: 10px 20px; background: #004b87; color: white; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; color: white; }
        .badge-qna { background: #e67e22; }
        .badge-mat { background: #27ae60; }
    </style>
</head>
<body>
    <div class="header"><h1>StudyChosun v2.0</h1><p>조선대학교 지식 공유 생태계</p></div>
    <div class="nav">
        <a href="/">홈 (과목선택)</a>
        <span style="float:right;">
        {% if session.user_id %}
            <b>{{ session.username }}</b>님 ({{ points }} P) | <a href="/logout">로그아웃</a>
        {% else %}
            <a href="/login">로그인/가입</a>
        {% endif %}
        </span>
    </div>
    {% with messages = get_flashed_messages() %}{% if messages %}
        {% for message in messages %}<div style="color:red; font-weight:bold; margin-bottom:10px;">{{ message }}</div>{% endfor %}
    {% endif %}{% endwith %}
    {% block content %}{% endblock %}
</body>
</html>
'''

def render(block_content, **kwargs):
    return render_template_string(BASE_HTML.replace('{% block content %}{% endblock %}', block_content), **kwargs)

# --- 라우팅 로직 ---

@app.route('/')
def index():
    html = '<h2>과목을 선택해 주세요</h2>'
    for code, name in SUBJECTS.items():
        html += f'<div class="subject-card" onclick="location.href=\'/subject/{code}\'"><h3>{name}</h3><p>Q&A 및 자료 공유</p></div>'
    return render(html)

@app.route('/subject/<sub_code>')
def subject_home(sub_code):
    sub_name = SUBJECTS.get(sub_code)
    html = f'''
    <h2>{sub_name} 게시판</h2>
    <div style="margin-bottom:30px;">
        <a href="/subject/{sub_code}/qna" class="btn" style="background:#e67e22;">Q&A 게시판 바로가기</a>
        <a href="/subject/{sub_code}/materials" class="btn" style="background:#27ae60;">자료공유 게시판 바로가기</a>
    </div>
    '''
    return render(html)

# --- [자료실 로직] ---

@app.route('/subject/<sub_code>/materials')
def material_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT m.*, u.username FROM materials m JOIN users u ON m.author_id = u.id WHERE m.subject=%s ORDER BY m.id DESC", (sub_code,))
    mats = c.fetchall()
    html = f'<h2>{SUBJECTS[sub_code]} 자료실</h2><a href="/subject/{sub_code}/materials/upload" class="btn">자료 업로드 (+20P 보상)</a><hr>'
    for m in mats:
        html += f'<div class="card"><h3>{m["title"]}</h3><p>작성자: {m["username"]} | 열람료: 10P</p>'
        html += f'<a href="/materials/view/{m["id"]}" class="btn">열람하기</a></div>'
    return render(html)

@app.route('/subject/<sub_code>/materials/upload', methods=['GET', 'POST'])
def material_upload(sub_code):
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        files = request.files.getlist('files')
        
        db = get_db(); c = db.cursor()
        # 1. 자료 정보 저장
        c.execute("INSERT INTO materials (subject, title, content, author_id) VALUES (%s, %s, %s, %s) RETURNING id",
                   (sub_code, title, content, session['user_id']))
        m_id = c.fetchone()[0]
        
        # 2. 다중 파일 Cloudinary 업로드
        for f in files:
            if f.filename:
                upload_result = cloudinary.uploader.upload(f)
                c.execute("INSERT INTO material_files (material_id, file_url, filename) VALUES (%s, %s, %s)",
                           (m_id, upload_result['secure_url'], f.filename))
        
        # 3. 업로드 보상 포인트 (+20P)
        c.execute("UPDATE users SET points = points + 20 WHERE id=%s", (session['user_id'],))
        db.commit()
        flash("자료가 등록되었습니다. 보상으로 20P가 지급되었습니다!")
        return redirect(url_for('material_list', sub_code=sub_code))

    return render(f'''
    <h2>{SUBJECTS[sub_code]} 자료 등록</h2>
    <form method="post" enctype="multipart/form-data" class="card">
        제목: <input type="text" name="title" style="width:100%;" required><br><br>
        설명: <textarea name="content" rows="5" style="width:100%;" required></textarea><br><br>
        파일 첨부(다중 선택 가능): <input type="file" name="files" multiple><br><br>
        <button type="submit" class="btn">자료 등록 (+20P 획득)</button>
    </form>
    ''')

@app.route('/materials/view/<int:m_id>')
def material_view(m_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    
    # 열람 기록 확인
    c.execute("SELECT * FROM material_views WHERE material_id=%s AND viewer_id=%s", (m_id, session['user_id']))
    already_viewed = c.fetchone()
    
    c.execute("SELECT m.*, u.points as author_points FROM materials m JOIN users u ON m.author_id = u.id WHERE m.id=%s", (m_id,))
    m = c.fetchone()

    if not already_viewed and m['author_id'] != session['user_id']:
        # 포인트 차감 및 지급 로직
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        if c.fetchone()['points'] < 10:
            flash("포인트가 부족합니다. (열람료 10P)")
            return redirect(url_for('index'))
        
        c.execute("UPDATE users SET points = points - 10 WHERE id=%s", (session['user_id'],)) # 열람자 -10
        c.execute("UPDATE users SET points = points + 5 WHERE id=%s", (m['author_id'],))   # 작성자 +5 (기여 보상)
        c.execute("INSERT INTO material_views (material_id, viewer_id) VALUES (%s, %s)", (m_id, session['user_id']))
        db.commit()
        flash("10P를 사용하여 자료를 열람합니다. 작성자에게 기여 보상 5P가 전달되었습니다.")

    # 자료 및 파일 정보 가져오기
    c.execute("SELECT * FROM material_files WHERE material_id=%s", (m_id,))
    files = c.fetchall()
    
    file_html = ""
    for f in files:
        if f['file_url'].lower().endswith(('jpg', 'jpeg', 'png', 'gif')):
            file_html += f'<img src="{f["file_url"]}" style="max-width:100%; margin-bottom:10px; border-radius:5px;"><br>'
        else:
            file_html += f'<a href="{f["file_url"]}" target="_blank">첨부파일 다운로드: {f["filename"]}</a><br>'

    return render(f'''
    <h2>{m['title']}</h2>
    <div class="card"><pre style="white-space: pre-wrap;">{m['content']}</pre></div>
    <div class="card"><h4>첨부 자료</h4>{file_html}</div>
    ''')

# --- [Q&A 로직] ---

@app.route('/subject/<sub_code>/qna')
def qna_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.subject=%s ORDER BY q.id DESC", (sub_code,))
    qs = c.fetchall()
    html = f'<h2>{SUBJECTS[sub_code]} Q&A</h2><a href="/subject/{sub_code}/qna/ask" class="btn">질문하기 (현상금 설정 가능)</a><hr>'
    for q in qs:
        status = "✅ 채택완료" if q['resolved'] else "답변 대기중"
        html += f'<div class="card"><h3><a href="/qna/view/{q["id"]}">{q["title"]}</a> <span style="color:red;">(+{q["bounty"]}P)</span></h3><p>{status} | 작성자: {q["username"]}</p></div>'
    return render(html)

@app.route('/subject/<sub_code>/qna/ask', methods=['GET', 'POST'])
def qna_ask(sub_code):
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        bounty = int(request.form.get('bounty', 0))
        db = get_db(); c = db.cursor()
        
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        if c.fetchone()['points'] < bounty:
            flash("현상금으로 걸 포인트가 부족합니다.")
            return redirect(request.url)
            
        c.execute("INSERT INTO qna (subject, title, content, bounty, author_id) VALUES (%s, %s, %s, %s, %s)",
                   (sub_code, request.form['title'], request.form['content'], bounty, session['user_id']))
        c.execute("UPDATE users SET points = points - %s WHERE id=%s", (bounty, session['user_id']))
        db.commit()
        return redirect(url_for('qna_list', sub_code=sub_code))
    
    return render(f'''
    <h2>{SUBJECTS[sub_code]} 질문 등록</h2>
    <form method="post" class="card">
        제목: <input type="text" name="title" style="width:100%;" required><br><br>
        내용: <textarea name="content" rows="5" style="width:100%;" required></textarea><br><br>
        추가 현상금(선택): <input type="number" name="bounty" value="0" min="0"> P<br><br>
        <button type="submit" class="btn">질문 등록</button>
    </form>
    ''')

@app.route('/qna/view/<int:q_id>', methods=['GET', 'POST'])
def qna_view(q_id):
    db = get_db(); c = db.cursor()
    if request.method == 'POST' and 'user_id' in session:
        # 답변 시 소량 보상 (+5P)
        c.execute("INSERT INTO answers (qna_id, content, author_id) VALUES (%s, %s, %s)", (q_id, request.form['content'], session['user_id']))
        c.execute("UPDATE users SET points = points + 5 WHERE id=%s", (session['user_id'],))
        db.commit()
        flash("답변을 등록했습니다. 참여 보상 5P가 지급되었습니다!")
        return redirect(request.url)

    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.id=%s", (q_id,)); q = c.fetchone()
    c.execute("SELECT a.*, u.username FROM answers a JOIN users u ON a.author_id = u.id WHERE a.qna_id=%s", (q_id,)); answers = c.fetchall()
    
    html = f'<h2>{q["title"]} <span style="color:red;">(현상금 {q["bounty"]}P)</span></h2><div class="card">{q["content"]}</div><h3>답변 목록</h3>'
    for a in answers:
        style = "border: 2px solid #004b87; background: #eaf4ff;" if a['accepted'] else ""
        accept_btn = ""
        if q['author_id'] == session.get('user_id') and not q['resolved']:
            accept_btn = f'<a href="/qna/accept/{a["id"]}" class="btn" style="background:#28a745; font-size:0.8em;">이 답변 채택하기</a>'
        
        html += f'<div class="card" style="{style}"><p><b>{a["username"]}</b>: {a["content"]}</p>{accept_btn}</div>'
    
    if 'user_id' in session and q['author_id'] != session['user_id']:
        html += '<form method="post"><textarea name="content" rows="3" style="width:100%;" placeholder="답변을 남겨주세요 (+5P)"></textarea><br><button class="btn">답변 등록</button></form>'
    return render(html)

@app.route('/qna/accept/<int:a_id>')
def qna_accept(a_id):
    db = get_db(); c = db.cursor()
    c.execute("SELECT a.*, q.bounty, q.id as q_id FROM answers a JOIN qna q ON a.qna_id = q.id WHERE a.id=%s", (a_id,))
    data = c.fetchone()
    # 채택 보상: 현상금 + 시스템 보상 20P
    c.execute("UPDATE answers SET accepted=1 WHERE id=%s", (a_id,))
    c.execute("UPDATE qna SET resolved=1 WHERE id=%s", (data['q_id'],))
    c.execute("UPDATE users SET points = points + %s WHERE id=%s", (data['bounty'] + 20, data['author_id']))
    db.commit()
    flash(f"답변을 채택했습니다! 답변자에게 {data['bounty'] + 20}P가 지급되었습니다.")
    return redirect(url_for('qna_view', q_id=data['q_id']))

# --- [인증 로직 (기존과 동일)] ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action, username, password = request.form.get('action'), request.form.get('username'), request.form.get('password')
        db = get_db(); c = db.cursor()
        if action == 'register':
            try:
                c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
                db.commit()
                flash("가입 성공! 100P가 지급되었습니다."); return redirect(url_for('login'))
            except: db.rollback(); flash("이미 존재하는 아이디입니다.")
        else:
            c.execute("SELECT id, username FROM users WHERE username=%s AND password=%s", (username, password))
            u = c.fetchone()
            if u: session['user_id'], session['username'] = u['id'], u['username']; return redirect(url_for('index'))
            flash("정보가 올바르지 않습니다.")
    return render('''<h2>로그인 / 회원가입</h2><form method="post" class="card">
        아이디: <input type="text" name="username" required><br>비밀번호: <input type="password" name="password" required><br><br>
        <button type="submit" name="action" value="login" class="btn">로그인</button>
        <button type="submit" name="action" value="register" class="btn" style="background:#28a745;">회원가입</button></form>''')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
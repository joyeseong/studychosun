import os
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template_string, request, redirect, url_for, session, g, flash
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chosun_secure_final')
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

# --- 포인트 및 정보 인젝터 ---
@app.context_processor
def inject_user_info():
    if 'user_id' in session:
        db = get_db(); c = db.cursor()
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        row = c.fetchone()
        return dict(points=row['points'] if row else 0, SUBJECTS=SUBJECTS)
    return dict(points=0, SUBJECTS=SUBJECTS)

# --- 공통 레이아웃 (타이틀 링크 및 설명 수정) ---
BASE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>StudyChosun</title>
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f9f9f9; color: #333; }
        .header { background: #004b87; color: white; padding: 30px; border-radius: 12px; text-align: center; margin-bottom: 25px; }
        .header a { text-decoration: none; color: white; }
        .header h1 { margin: 0; font-size: 2.5em; letter-spacing: -1px; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; font-size: 1.1em; }
        
        .nav { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }
        .nav a { text-decoration: none; color: #555; font-weight: bold; font-size: 0.95em; }
        .nav a:hover { color: #004b87; }
        
        .subject-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 20px; }
        .subject-card { width: calc(33% - 20px); background: white; padding: 40px 20px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; cursor: pointer; transition: all 0.3s ease; border: 1px solid #eee; }
        .subject-card:hover { transform: translateY(-8px); border-color: #004b87; box-shadow: 0 8px 25px rgba(0,75,135,0.15); }
        .subject-card h3 { margin: 0; color: #004b87; font-size: 1.3em; }
        
        .card { background: white; border: 1px solid #eee; padding: 25px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
        .btn { padding: 12px 24px; background: #004b87; color: white; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; font-weight: bold; transition: background 0.2s; }
        .btn:hover { background: #003663; }
        
        pre { background: #f4f4f4; padding: 15px; border-radius: 5px; font-family: inherit; font-size: 1em; }
    </style>
</head>
<body>
    <div class="header">
        <a href="/"><h1>StudyChosun</h1></a>
        <p>조선대학교 공부 커뮤니티</p>
    </div>
    <div class="nav">
        <a href="/">홈 (과목선택)</a>
        <div>
        {% if session.user_id %}
            <span style="margin-right:15px;"><b>{{ session.username }}</b>님 ({{ points }} P)</span>
            <a href="/logout" style="color:#d9534f;">로그아웃</a>
        {% else %}
            <a href="/login">로그인 / 회원가입</a>
        {% endif %}
        </div>
    </div>
    {% with messages = get_flashed_messages() %}{% if messages %}
        {% for message in messages %}<div style="color:#d9534f; background:#fdf7f7; padding:10px; border-radius:5px; margin-bottom:20px; border:1px solid #eed3d7;">{{ message }}</div>{% endfor %}
    {% endif %}{% endwith %}
    {% block content %}{% endblock %}
</body>
</html>
'''

def render(block_content, **kwargs):
    return render_template_string(BASE_HTML.replace('{% block content %}{% endblock %}', block_content), **kwargs)

# --- 라우팅 (과목명만 노출되도록 수정) ---

@app.route('/')
def index():
    html = '<h2 style="text-align:center; color:#555; margin-bottom:30px;">수강 과목을 선택하세요</h2>'
    html += '<div class="subject-container">'
    for code, name in SUBJECTS.items():
        html += f'<div class="subject-card" onclick="location.href=\'/subject/{code}\'"><h3>{name}</h3></div>'
    html += '</div>'
    return render(html)

@app.route('/subject/<sub_code>')
def subject_home(sub_code):
    sub_name = SUBJECTS.get(sub_code)
    html = f'''
    <h2 style="margin-top:0;">{sub_name}</h2>
    <div style="display:flex; gap:20px; margin-top:30px;">
        <div class="card" style="flex:1; text-align:center;">
            <h3>질문과 답변</h3>
            <p>모르는 문제를 물어보고 포인트를 획득하세요.</p>
            <a href="/subject/{sub_code}/qna" class="btn" style="background:#e67e22; width:80%;">Q&A 입장</a>
        </div>
        <div class="card" style="flex:1; text-align:center;">
            <h3>자료 공유</h3>
            <p>정리 노트를 공유하고 기여 보상을 받으세요.</p>
            <a href="/subject/{sub_code}/materials" class="btn" style="background:#27ae60; width:80%;">자료실 입장</a>
        </div>
    </div>
    '''
    return render(html)

# --- [자료실/Q&A 로직은 이전과 동일하되 URL 처리 유지] ---

@app.route('/subject/<sub_code>/materials')
def material_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT m.*, u.username FROM materials m JOIN users u ON m.author_id = u.id WHERE m.subject=%s ORDER BY m.id DESC", (sub_code,))
    mats = c.fetchall()
    html = f'<h2>{SUBJECTS[sub_code]} 자료실</h2><a href="/subject/{sub_code}/materials/upload" class="btn">자료 업로드 (+20P 보상)</a><hr style="border:0; border-top:1px solid #eee; margin:20px 0;">'
    for m in mats:
        html += f'<div class="card"><h3>{m["title"]}</h3><p style="color:#777;">작성자: {m["username"]} | 열람료: 10P</p>'
        html += f'<a href="/materials/view/{m["id"]}" class="btn">자료 열람하기</a></div>'
    return render(html)

@app.route('/subject/<sub_code>/materials/upload', methods=['GET', 'POST'])
def material_upload(sub_code):
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        title, content = request.form['title'], request.form['content']
        files = request.files.getlist('files')
        db = get_db(); c = db.cursor()
        c.execute("INSERT INTO materials (subject, title, content, author_id) VALUES (%s, %s, %s, %s) RETURNING id", (sub_code, title, content, session['user_id']))
        m_id = c.fetchone()[0]
        for f in files:
            if f.filename:
                res = cloudinary.uploader.upload(f)
                c.execute("INSERT INTO material_files (material_id, file_url, filename) VALUES (%s, %s, %s)", (m_id, res['secure_url'], f.filename))
        c.execute("UPDATE users SET points = points + 20 WHERE id=%s", (session['user_id'],))
        db.commit()
        flash("자료가 등록되었습니다. 보상으로 20P가 지급되었습니다!"); return redirect(url_for('material_list', sub_code=sub_code))
    return render(f'''<h2>{SUBJECTS[sub_code]} 자료 등록</h2><form method="post" enctype="multipart/form-data" class="card">
        제목: <input type="text" name="title" style="width:100%; padding:10px; border-radius:5px; border:1px solid #ddd;" required><br><br>
        설명: <textarea name="content" rows="8" style="width:100%; padding:10px; border-radius:5px; border:1px solid #ddd;" required></textarea><br><br>
        파일 첨부 (이미지/문서): <input type="file" name="files" multiple><br><br>
        <button type="submit" class="btn">자료 등록 완료</button></form>''')

@app.route('/materials/view/<int:m_id>')
def material_view(m_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    c.execute("SELECT * FROM material_views WHERE material_id=%s AND viewer_id=%s", (m_id, session['user_id']))
    already = c.fetchone()
    c.execute("SELECT m.*, u.points as author_points FROM materials m JOIN users u ON m.author_id = u.id WHERE m.id=%s", (m_id,))
    m = c.fetchone()
    
    if not already and m['author_id'] != session['user_id']:
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        if c.fetchone()['points'] < 10: flash("포인트가 부족합니다."); return redirect(url_for('index'))
        c.execute("UPDATE users SET points = points - 10 WHERE id=%s", (session['user_id'],))
        c.execute("UPDATE users SET points = points + 5 WHERE id=%s", (m['author_id'],))
        c.execute("INSERT INTO material_views (material_id, viewer_id) VALUES (%s, %s)", (m_id, session['user_id']))
        db.commit()
        flash("10P를 소모하여 자료를 열람합니다. 작성자에게 5P가 보상으로 지급되었습니다.")
        
    c.execute("SELECT * FROM material_files WHERE material_id=%s", (m_id,))
    files = c.fetchall()
    file_html = ""
    for f in files:
        if f['file_url'].lower().endswith(('jpg', 'jpeg', 'png', 'gif')):
            file_html += f'<img src="{f["file_url"]}" style="max-width:100%; margin-top:20px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.1);"><br>'
        else:
            file_html += f'<div style="margin-top:15px;"><a href="{f["file_url"]}" target="_blank" class="btn" style="background:#555;">첨부파일 다운로드: {f["filename"]}</a></div>'
            
    # 본인이 작성한 글일 경우에만 삭제 버튼 노출
    delete_btn = ""
    if m['author_id'] == session['user_id']:
        delete_btn = f'''
        <form method="post" action="/materials/delete/{m_id}" style="display:inline; float:right;" onsubmit="return confirm('정말로 이 자료를 삭제하시겠습니까?');">
            <button type="submit" class="btn" style="background:#d9534f; padding:8px 16px;">자료 삭제</button>
        </form>
        '''
            
    return render(f'''
    <div style="overflow:hidden; margin-bottom:15px;">
        <h2 style="float:left; margin:0;">{m["title"]}</h2>
        {delete_btn}
    </div>
    <div class="card"><pre>{m["content"]}</pre></div>
    <div class="card"><h4>첨부 자료</h4>{file_html}</div>
    <div style="margin-top:20px;">
        <a href="/subject/{m["subject"]}/materials" class="btn" style="background:#777;">목록으로 돌아가기</a>
    </div>
    ''')

# --- 새로 추가되는 삭제 라우팅 ---
@app.route('/materials/delete/<int:m_id>', methods=['POST'])
def material_delete(m_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    
    # 권한 확인을 위해 게시글 정보 가져오기
    c.execute("SELECT author_id, subject FROM materials WHERE id=%s", (m_id,))
    m = c.fetchone()
    
    if not m or m['author_id'] != session['user_id']:
        flash("삭제 권한이 없습니다.")
        return redirect(url_for('index'))
        
    # 하위 데이터(열람 기록, 파일 URL) 먼저 삭제 후 메인 게시글 삭제
    c.execute("DELETE FROM material_views WHERE material_id=%s", (m_id,))
    c.execute("DELETE FROM material_files WHERE material_id=%s", (m_id,))
    c.execute("DELETE FROM materials WHERE id=%s", (m_id,))
    db.commit()
    
    flash("자료가 성공적으로 삭제되었습니다.")
    return redirect(url_for('material_list', sub_code=m['subject']))

@app.route('/subject/<sub_code>/qna')
def qna_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.subject=%s ORDER BY q.id DESC", (sub_code,))
    qs = c.fetchall()
    html = f'<h2>{SUBJECTS[sub_code]} Q&A</h2><a href="/subject/{sub_code}/qna/ask" class="btn" style="background:#e67e22;">질문 등록하기</a><hr style="border:0; border-top:1px solid #eee; margin:20px 0;">'
    for q in qs:
        status = "✅ 채택완료" if q['resolved'] else "답변 대기중"
        html += f'<div class="card"><h3><a href="/qna/view/{q["id"]}" style="text-decoration:none; color:#333;">{q["title"]}</a> <span style="color:#d9534f; font-size:0.8em;">(+{q["bounty"]}P)</span></h3><p style="color:#777;">{status} | 작성자: {q["username"]}</p></div>'
    return render(html)

@app.route('/subject/<sub_code>/qna/ask', methods=['GET', 'POST'])
def qna_ask(sub_code):
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        bounty = int(request.form.get('bounty', 0))
        db = get_db(); c = db.cursor()
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        if c.fetchone()['points'] < bounty: flash("보유 포인트가 부족합니다."); return redirect(request.url)
        c.execute("INSERT INTO qna (subject, title, content, bounty, author_id) VALUES (%s, %s, %s, %s, %s)", (sub_code, request.form['title'], request.form['content'], bounty, session['user_id']))
        c.execute("UPDATE users SET points = points - %s WHERE id=%s", (bounty, session['user_id']))
        db.commit(); return redirect(url_for('qna_list', sub_code=sub_code))
    return render(f'<h2>질문 등록</h2><form method="post" class="card">제목: <input type="text" name="title" style="width:100%; padding:10px; border-radius:5px; border:1px solid #ddd;" required><br><br>내용: <textarea name="content" rows="8" style="width:100%; padding:10px; border-radius:5px; border:1px solid #ddd;" required></textarea><br><br>추가 현상금: <input type="number" name="bounty" value="0" min="0"> P<br><br><button type="submit" class="btn" style="background:#e67e22;">질문 올리기</button></form>')

@app.route('/qna/view/<int:q_id>', methods=['GET', 'POST'])
def qna_view(q_id):
    db = get_db(); c = db.cursor()
    if request.method == 'POST' and 'user_id' in session:
        c.execute("INSERT INTO answers (qna_id, content, author_id) VALUES (%s, %s, %s)", (q_id, request.form['content'], session['user_id']))
        c.execute("UPDATE users SET points = points + 5 WHERE id=%s", (session['user_id'],))
        db.commit(); flash("답변 참여 보상 5P가 지급되었습니다!"); return redirect(request.url)
    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.id=%s", (q_id,)); q = c.fetchone()
    c.execute("SELECT a.*, u.username FROM answers a JOIN users u ON a.author_id = u.id WHERE a.qna_id=%s ORDER BY a.id ASC", (q_id,)); answers = c.fetchall()
    html = f'<h2>{q["title"]} <span style="color:#d9534f;">(+{q["bounty"]}P)</span></h2><div class="card"><pre>{q["content"]}</pre></div><h3>답변</h3>'
    for a in answers:
        style = "border: 2px solid #004b87; background: #f0f7ff;" if a['accepted'] else ""
        btn = f'<a href="/qna/accept/{a["id"]}" class="btn" style="background:#28a745; font-size:0.8em; margin-top:10px;">채택하기</a>' if q['author_id'] == session.get('user_id') and not q['resolved'] else ""
        html += f'<div class="card" style="{style}"><b>{a["username"]}</b><p>{a["content"]}</p>{btn}</div>'
    if 'user_id' in session and q['author_id'] != session['user_id']:
        html += '<form method="post" class="card"><h4>답변 남기기</h4><textarea name="content" rows="4" style="width:100%; padding:10px; border-radius:5px; border:1px solid #ddd;" placeholder="답변을 작성하면 5P를 받습니다."></textarea><br><button class="btn">답변 등록</button></form>'
    return render(html)

@app.route('/qna/accept/<int:a_id>')
def qna_accept(a_id):
    db = get_db(); c = db.cursor()
    c.execute("SELECT a.*, q.bounty, q.id as q_id FROM answers a JOIN qna q ON a.qna_id = q.id WHERE a.id=%s", (a_id,))
    data = c.fetchone()
    c.execute("UPDATE answers SET accepted=1 WHERE id=%s", (a_id,))
    c.execute("UPDATE qna SET resolved=1 WHERE id=%s", (data['q_id'],))
    c.execute("UPDATE users SET points = points + %s WHERE id=%s", (data['bounty'] + 20, data['author_id']))
    db.commit(); flash(f"답변을 채택했습니다! 보상 {data['bounty'] + 20}P가 지급되었습니다."); return redirect(url_for('qna_view', q_id=data['q_id']))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        act, user, pwd = request.form.get('action'), request.form.get('username'), request.form.get('password')
        db = get_db(); c = db.cursor()
        if act == 'register':
            try:
                c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (user, pwd))
                db.commit(); flash("회원가입 완료! 로그인 해주세요."); return redirect(url_for('login'))
            except: db.rollback(); flash("이미 사용 중인 아이디입니다.")
        else:
            c.execute("SELECT id, username FROM users WHERE username=%s AND password=%s", (user, pwd))
            u = c.fetchone()
            if u: session['user_id'], session['username'] = u['id'], u['username']; return redirect(url_for('index'))
            flash("아이디 또는 비밀번호가 틀립니다.")
    return render('''<div style="max-width:400px; margin:0 auto;"><h2>로그인 / 회원가입</h2><form method="post" class="card">
        아이디: <input type="text" name="username" style="width:90%; padding:8px; margin-bottom:10px;" required><br>
        비밀번호: <input type="password" name="password" style="width:90%; padding:8px; margin-bottom:20px;" required><br>
        <button type="submit" name="action" value="login" class="btn" style="width:100%; margin-bottom:10px;">로그인</button>
        <button type="submit" name="action" value="register" class="btn" style="width:100%; background:#28a745;">회원가입</button></form></div>''')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
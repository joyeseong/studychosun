import os
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import psycopg2
from psycopg2.extras import DictCursor

# --- Render 환경변수 설정 ---
app = Flask(__name__)
# 세션 암호화를 위해 비밀키를 사용
app.secret_key = os.environ.get('SECRET_KEY')
# DB에 접속하기 위한 주소를 환경변수로 설정
DATABASE_URL = os.environ.get('DATABASE_URL')
# Cloudinary 접속 주소를 환경변수로 설정
cloudinary.config(cloudinary_url=os.environ.get('CLOUDINARY_URL'))

# 운영할 과목 리스트 정의
SUBJECTS = {
    'computer_networks': '컴퓨터네트워크',
    'deep_learning': '딥러닝기초',
    'software_engineering': '소프트웨어공학',
    'fullstack': '풀스택개발및응용',
    'security': '인터넷보안'
}

# --- DB 연결 함수 ---
# DB랑 통신하기 위해 Flask의 임시 보관소 변수 g를 이용, g에 db가 있으면 그대로 리턴하고, 없으면 db를 딕셔너리 형태로 가져온다.
def get_db():
    if not hasattr(g, '_database'):
        g._database = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return g._database

# 사용자의 요청이 끝날때, g를 닫아준다.
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

# HTML 렌더링 전, 실행되는 함수
# 여기서 HTML의 모든 화면에 공통 변수를 주입한다. ( 현재 = 유저 포인트, 과목 )
@app.context_processor
def inject_global_var():
    if 'user_id' in session:
        db = get_db(); c = db.cursor()
        c.execute("SELECT points FROM users WHERE id=%s", (session['user_id'],))
        row = c.fetchone()
        return dict(points=row['points'] if row else 0, SUBJECTS=SUBJECTS)
    return dict(points=0, SUBJECTS=SUBJECTS)

# --- 컨트롤러 로직 (기존 HTML 뼈대 및 렌더링 함수는 render_template으로 대체됨) ---

# 홈 화면
@app.route('/')
def index():
    return render_template('index.html')

# 과목 세부 게시판
@app.route('/subject/<sub_code>')
def subject_home(sub_code):
    sub_name = SUBJECTS.get(sub_code)
    return render_template('subject.html', sub_code=sub_code, sub_name=sub_name)

# 공부 자료실
@app.route('/subject/<sub_code>/materials')
def material_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT m.*, u.username FROM materials m JOIN users u ON m.author_id = u.id WHERE m.subject=%s ORDER BY m.id DESC", (sub_code,))
    mats = c.fetchall()
    return render_template('material_list.html', sub_code=sub_code, mats=mats)

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
    return render_template('material_upload.html', sub_code=sub_code)

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
    
    # 이미지 여부 판별 로직 추가 (프론트엔드 노출용)
    for f in files:
        f['is_image'] = f['file_url'].lower().endswith(('jpg', 'jpeg', 'png', 'gif'))
            
    return render_template('material_view.html', m=m, files=files)

# 삭제 메소드
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

# QnA 게시판
@app.route('/subject/<sub_code>/qna')
def qna_list(sub_code):
    db = get_db(); c = db.cursor()
    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.subject=%s ORDER BY q.id DESC", (sub_code,))
    qs = c.fetchall()
    return render_template('qna_list.html', sub_code=sub_code, qs=qs)

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
    return render_template('qna_ask.html', sub_code=sub_code)

@app.route('/qna/view/<int:q_id>', methods=['GET', 'POST'])
def qna_view(q_id):
    db = get_db(); c = db.cursor()
    
    if request.method == 'POST' and 'user_id' in session:
        # 중복 답변 체크 (이 질문에 이미 답변을 단 적이 있는지 확인)
        c.execute("SELECT COUNT(*) as cnt FROM answers WHERE qna_id=%s AND author_id=%s", (q_id, session['user_id']))
        already_answered = c.fetchone()['cnt'] > 0
        
        c.execute("INSERT INTO answers (qna_id, content, author_id) VALUES (%s, %s, %s)", (q_id, request.form['content'], session['user_id']))
        
        # 첫 답변일 때만 포인트 지급
        if not already_answered:
            c.execute("UPDATE users SET points = points + 5 WHERE id=%s", (session['user_id'],))
            flash("답변 등록 완료! 첫 답변 보상 5P가 지급되었습니다.")
        else:
            flash("답변이 추가로 등록되었습니다. (참여 보상은 질문당 1회만 지급됩니다)")
            
        db.commit()
        return redirect(request.url)

    c.execute("SELECT q.*, u.username FROM qna q JOIN users u ON q.author_id = u.id WHERE q.id=%s", (q_id,)); q = c.fetchone()
    c.execute("SELECT a.*, u.username FROM answers a JOIN users u ON a.author_id = u.id WHERE a.qna_id=%s ORDER BY a.id ASC", (q_id,)); answers = c.fetchall()
    
    return render_template('qna_view.html', q=q, answers=answers)
    
@app.route('/qna/delete/<int:q_id>', methods=['POST'])
def qna_delete(q_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    
    # 질문 정보와 답변 개수 확인
    c.execute("SELECT * FROM qna WHERE id=%s", (q_id,))
    q = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM answers WHERE qna_id=%s", (q_id,))
    ans_count = c.fetchone()['cnt']
    
    # 예외 처리 (권한 없음, 답변 달림)
    if not q or q['author_id'] != session['user_id']:
        flash("삭제 권한이 없습니다."); return redirect(url_for('index'))
    if ans_count > 0:
        flash("이미 답변이 달린 질문은 삭제할 수 없습니다."); return redirect(url_for('qna_view', q_id=q_id))
        
    # 질문 삭제 진행 및 현상금 반환
    c.execute("UPDATE users SET points = points + %s WHERE id=%s", (q['bounty'], session['user_id']))
    c.execute("DELETE FROM qna WHERE id=%s", (q_id,))
    db.commit()
    
    flash(f"질문이 삭제되었으며, 걸어두었던 현상금 {q['bounty']}P가 반환되었습니다.")
    return redirect(url_for('qna_list', sub_code=q['subject']))

@app.route('/answers/delete/<int:a_id>', methods=['POST'])
def answer_delete(a_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db(); c = db.cursor()
    
    c.execute("SELECT a.*, q.id as q_id FROM answers a JOIN qna q ON a.qna_id = q.id WHERE a.id=%s", (a_id,))
    a = c.fetchone()
    
    # 예외 처리 (권한 없음, 이미 채택됨)
    if not a or a['author_id'] != session['user_id']:
        flash("삭제 권한이 없습니다."); return redirect(url_for('index'))
    if a['accepted']:
        flash("이미 채택된 답변은 게시판 보존을 위해 삭제할 수 없습니다."); return redirect(url_for('qna_view', q_id=a['q_id']))
        
    c.execute("DELETE FROM answers WHERE id=%s", (a_id,))
    db.commit()
    
    flash("답변이 삭제되었습니다.")
    return redirect(url_for('qna_view', q_id=a['q_id']))

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
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
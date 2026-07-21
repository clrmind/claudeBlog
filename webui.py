#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoBlogger 웹 컨트롤 패널
==========================
Termux에서 실행하는 Flask 웹서버. 폰 브라우저(안드로이드/아이폰)로 접속해
키워드 발행, 이미지 첨부, 설정 관리, 스케줄 관리, 로그 확인을 할 수 있다.

실행:
  pip install flask
  python webui.py
  → 폰 브라우저에서 http://localhost:8080 접속
    (다른 기기(아이폰 등)에서 접속하려면 http://<폰_IP>:8080, 같은 WiFi 필요)

비밀번호:
  최초 실행 시 콘솔에 임시 비밀번호가 출력됩니다.
  config.json의 "webui_password" 또는 환경변수 WEBUI_PASSWORD로 고정할 수 있습니다.
"""

import datetime
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time

from flask import (Flask, redirect, render_template_string, request,
                   session, url_for, jsonify)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
DATA_PATH = os.path.join(BASE_DIR, "posts", "data.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RUN_LOG = os.path.join(BASE_DIR, "webui_run.log")
SECRET_FILE = os.path.join(BASE_DIR, ".webui_secret")
PYTHON = sys.executable or "python"

app = Flask(__name__)

# 세션 시크릿 (재시작해도 유지되도록 파일에 저장)
if os.path.exists(SECRET_FILE):
    app.secret_key = open(SECRET_FILE).read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    try:
        with open(SECRET_FILE, "w") as f:
            f.write(app.secret_key)
        os.chmod(SECRET_FILE, 0o600)
    except Exception:
        pass

# 실행 상태 (한 번에 하나만 발행)
_run_state = {"running": False, "started": None, "cmd": ""}


# ==========================================
# 설정/환경 파일 헬퍼
# ==========================================

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            return json.load(open(CONFIG_PATH, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip("'\"")
    return env


def save_env(env):
    lines = ["# AutoBlogger 비밀 키 (절대 커밋되지 않음)"]
    for k, v in env.items():
        lines.append(f"{k}={v}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(ENV_PATH, 0o600)
    except Exception:
        pass


def get_password():
    return (os.environ.get("WEBUI_PASSWORD")
            or load_config().get("webui_password")
            or _TEMP_PASSWORD)


def load_posts():
    if os.path.exists(DATA_PATH):
        try:
            return json.load(open(DATA_PATH, encoding="utf-8"))
        except Exception:
            return []
    return []


def git_remote_url():
    try:
        return subprocess.run(["git", "remote", "get-url", "origin"], cwd=BASE_DIR,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def set_git_remote_url(url):
    subprocess.run(["git", "remote", "set-url", "origin", url], cwd=BASE_DIR)


# ==========================================
# 발행 실행 (백그라운드)
# ==========================================

def run_publish(args_list):
    """autoblogger.py를 백그라운드로 실행하고 로그를 파일에 남긴다."""
    def worker():
        _run_state.update(running=True, started=time.time(),
                          cmd=" ".join(args_list))
        with open(RUN_LOG, "w", encoding="utf-8") as log:
            log.write(f"$ {' '.join(args_list)}\n\n")
            log.flush()
            try:
                p = subprocess.Popen(args_list, cwd=BASE_DIR, stdout=log,
                                     stderr=subprocess.STDOUT)
                p.wait()
                log.write(f"\n\n=== 종료 코드: {p.returncode} ===\n")
            except Exception as e:
                log.write(f"\n\n❌ 실행 오류: {e}\n")
        _run_state.update(running=False)
    t = threading.Thread(target=worker, daemon=True)
    t.start()


def read_run_log():
    if os.path.exists(RUN_LOG):
        return open(RUN_LOG, encoding="utf-8").read()
    return "(아직 실행 기록 없음)"


# ==========================================
# 크론(스케줄) 헬퍼
# ==========================================

def crontab_lines():
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if out.returncode != 0:
            return []
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def write_crontab(lines):
    content = "\n".join(lines) + "\n" if lines else ""
    subprocess.run(["crontab", "-"], input=content, text=True)


def parse_blog_schedules():
    """autoblogger를 실행하는 크론 줄만 골라 [{raw, hour, minute, source, disabled}]로 파싱."""
    result = []
    for line in crontab_lines():
        if "autoblogger.py" not in line:
            continue
        disabled = line.strip().startswith("#")
        core = line.lstrip("#").strip()
        m = re.match(r"(\S+)\s+(\S+)\s+\S+\s+\S+\s+\S+\s+(.*)", core)
        if not m:
            continue
        minute, hour, cmd = m.group(1), m.group(2), m.group(3)
        source = "tv" if "--source tv" in cmd else "trends"
        result.append({"raw": line, "hour": hour, "minute": minute,
                       "source": source, "disabled": disabled})
    return result


def build_cron_line(hour, minute, source):
    src = " --source tv" if source == "tv" else ""
    return (f"{minute} {hour} * * * cd {BASE_DIR} && {PYTHON} autoblogger.py{src} "
            f">> auto_run.log 2>&1")


def add_schedule(hour, minute, source):
    lines = crontab_lines()
    lines.append(build_cron_line(hour, minute, source))
    write_crontab(lines)


def remove_schedule(raw):
    lines = [l for l in crontab_lines() if l.strip() != raw.strip()]
    write_crontab(lines)


# ==========================================
# HTML (모바일 우선, 깔끔)
# ==========================================

BASE_HTML = """
<!DOCTYPE html><html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>{{ title }} · AutoBlogger</title>
<style>
:root { --green:#00c73c; --green-d:#00a835; --bg:#f5f6f8; --card:#fff; --line:#e8eaed; --txt:#222; --sub:#777; }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
body { margin:0; font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  background:var(--bg); color:var(--txt); padding-bottom:80px; line-height:1.5; }
header { background:var(--green); color:#fff; padding:16px 18px; font-size:19px; font-weight:800;
  position:sticky; top:0; z-index:10; display:flex; justify-content:space-between; align-items:center; }
header .sub { font-size:12px; font-weight:500; opacity:.9; }
.wrap { max-width:640px; margin:0 auto; padding:16px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; margin-bottom:16px; }
.card h2 { margin:0 0 14px; font-size:16px; }
label { display:block; font-size:13px; color:var(--sub); margin:12px 0 6px; font-weight:600; }
input[type=text], input[type=password], input[type=number], input[type=time], select, textarea {
  width:100%; padding:13px 14px; font-size:16px; border:1px solid var(--line); border-radius:10px;
  background:#fff; outline:none; }
input:focus, select:focus, textarea:focus { border-color:var(--green); }
textarea { min-height:80px; resize:vertical; }
.btn { display:block; width:100%; padding:15px; font-size:16px; font-weight:700; border:none;
  border-radius:12px; background:var(--green); color:#fff; cursor:pointer; margin-top:16px; }
.btn:active { background:var(--green-d); }
.btn.gray { background:#eceef1; color:#444; }
.btn.sm { width:auto; padding:9px 14px; font-size:14px; margin:0; display:inline-block; }
.btn.red { background:#ff4d4f; }
.row { display:flex; gap:10px; align-items:center; }
.row > * { flex:1; }
.pill { display:inline-block; background:#e2fbf0; color:var(--green-d); border-radius:20px;
  padding:4px 12px; font-size:12px; font-weight:700; }
.muted { color:var(--sub); font-size:13px; }
.post { display:flex; gap:12px; align-items:center; padding:10px 0; border-bottom:1px solid var(--line); }
.post:last-child { border-bottom:none; }
.post img { width:52px; height:52px; border-radius:8px; object-fit:cover; background:#eee; }
.post .t { font-size:14px; font-weight:600; line-height:1.35; }
.nav { position:fixed; bottom:0; left:0; right:0; background:#fff; border-top:1px solid var(--line);
  display:flex; z-index:20; }
.nav a { flex:1; text-align:center; padding:10px 0 12px; text-decoration:none; color:var(--sub);
  font-size:11px; font-weight:600; }
.nav a.active { color:var(--green); }
.nav a .ic { display:block; font-size:20px; margin-bottom:2px; }
.flash { background:#e2fbf0; color:var(--green-d); border:1px solid #b8ecd0; padding:12px 14px;
  border-radius:10px; margin-bottom:14px; font-size:14px; }
.flash.err { background:#ffe9e9; color:#c0392b; border-color:#f5c6c6; }
pre { background:#0f1720; color:#d6e2ee; padding:14px; border-radius:10px; overflow-x:auto;
  font-size:12px; white-space:pre-wrap; word-break:break-all; max-height:60vh; }
.switch { display:flex; align-items:center; gap:8px; }
small.hint { color:var(--sub); font-size:12px; display:block; margin-top:4px; }
</style></head><body>
<header><span>🤖 AutoBlogger</span><span class="sub">{{ domain }}</span></header>
<div class="wrap">
{% if flash %}<div class="flash {{ 'err' if flash_err else '' }}">{{ flash }}</div>{% endif %}
{{ body|safe }}
</div>
<div class="nav">
  <a href="/" class="{{ 'active' if tab=='home' else '' }}"><span class="ic">🏠</span>홈</a>
  <a href="/new" class="{{ 'active' if tab=='new' else '' }}"><span class="ic">✍️</span>새 글</a>
  <a href="/schedule" class="{{ 'active' if tab=='schedule' else '' }}"><span class="ic">⏰</span>스케줄</a>
  <a href="/settings" class="{{ 'active' if tab=='settings' else '' }}"><span class="ic">⚙️</span>설정</a>
  <a href="/logs" class="{{ 'active' if tab=='logs' else '' }}"><span class="ic">📋</span>로그</a>
</div>
</body></html>
"""

LOGIN_HTML = """
<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>로그인 · AutoBlogger</title>
<style>
body{margin:0;font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;background:#00c73c;
 display:flex;align-items:center;justify-content:center;height:100vh;}
.box{background:#fff;padding:32px 26px;border-radius:18px;width:88%;max-width:340px;text-align:center;
 box-shadow:0 10px 40px rgba(0,0,0,.15);}
h1{font-size:22px;margin:0 0 6px;}p{color:#888;font-size:13px;margin:0 0 20px;}
input{width:100%;padding:14px;font-size:16px;border:1px solid #e5e7eb;border-radius:10px;box-sizing:border-box;}
button{width:100%;padding:14px;font-size:16px;font-weight:700;border:none;border-radius:10px;
 background:#00c73c;color:#fff;margin-top:14px;}
.err{color:#c0392b;font-size:13px;margin-top:12px;}
</style></head><body>
<form class="box" method="post">
<h1>🤖 AutoBlogger</h1><p>컨트롤 패널 로그인</p>
<input type="password" name="password" placeholder="비밀번호" autofocus>
<button type="submit">로그인</button>
{% if err %}<div class="err">{{ err }}</div>{% endif %}
</form></body></html>
"""


def render(title, tab, body, flash=None, flash_err=False):
    cfg = load_config()
    return render_template_string(
        BASE_HTML, title=title, tab=tab, body=body, flash=flash,
        flash_err=flash_err, domain=cfg.get("blog_domain", "").replace("https://", ""))


# ==========================================
# 인증
# ==========================================

def logged_in():
    return session.get("auth") is True


@app.before_request
def require_login():
    if request.endpoint in ("login", "static"):
        return
    if not logged_in():
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    err = ""
    if request.method == "POST":
        if request.form.get("password") == get_password():
            session["auth"] = True
            session.permanent = True
            return redirect(url_for("home"))
        err = "비밀번호가 틀렸습니다."
    return render_template_string(LOGIN_HTML, err=err)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# 홈 (대시보드)
# ==========================================

@app.route("/")
def home():
    cfg = load_config()
    posts = load_posts()
    today = datetime.date.today().isoformat()
    today_count = sum(1 for p in posts if p.get("date") == today)
    limit = cfg.get("max_posts_per_day", 3)
    recent = sorted(posts, key=lambda x: x.get("filename", ""), reverse=True)[:5]

    running = _run_state["running"]
    status_card = (
        f"<div class='card'><h2>상태</h2>"
        f"<div class='row'><div><div class='muted'>오늘 발행</div>"
        f"<div style='font-size:24px;font-weight:800'>{today_count} / {limit}</div></div>"
        f"<div><div class='muted'>전체 글</div>"
        f"<div style='font-size:24px;font-weight:800'>{len(posts)}</div></div>"
        f"<div><div class='muted'>발행 상태</div>"
        f"<div style='font-size:16px;font-weight:800;margin-top:6px'>"
        f"{'🟢 실행 중' if running else '⚪ 대기'}</div></div></div>"
        + ("<a class='btn' href='/logs'>진행 로그 보기</a>" if running else "")
        + "</div>"
    )

    quick = (
        "<div class='card'><h2>빠른 실행</h2>"
        "<form method='post' action='/publish'>"
        "<input type='hidden' name='mode' value='auto'>"
        "<label>키워드 소스</label>"
        "<select name='source'>"
        f"<option value='trends'>실시간 트렌드</option>"
        f"<option value='tv'>방송 건강·식품</option></select>"
        "<button class='btn' type='submit'>지금 자동 발행 ▶</button>"
        "<small class='hint'>AI가 키워드를 자동 선정해 글을 씁니다.</small>"
        "</form></div>"
    )

    items = "".join(
        f"<div class='post'><img src='{cfg.get('blog_domain','')}{p['image']}' "
        f"onerror=\"this.style.visibility='hidden'\">"
        f"<div><div class='t'>{p['title']}</div>"
        f"<div class='muted'>{p['date']}</div></div></div>"
        if not str(p.get("image", "")).startswith("http") else
        f"<div class='post'><img src='{p['image']}' onerror=\"this.style.visibility='hidden'\">"
        f"<div><div class='t'>{p['title']}</div>"
        f"<div class='muted'>{p['date']}</div></div></div>"
        for p in recent
    ) or "<div class='muted'>아직 글이 없습니다.</div>"
    recent_card = f"<div class='card'><h2>최근 글</h2>{items}</div>"

    return render("홈", "home", status_card + quick + recent_card)


# ==========================================
# 새 글 (수동 발행 + 이미지 첨부)
# ==========================================

@app.route("/new")
def new_post():
    body = """
    <div class='card'><h2>✍️ 직접 글쓰기</h2>
    <form method='post' action='/publish' enctype='multipart/form-data'>
      <input type='hidden' name='mode' value='keyword'>
      <label>키워드 (필수)</label>
      <input type='text' name='keyword' placeholder='예: 갱년기 영양제 추천' required>
      <label>제목 직접 지정 (선택)</label>
      <input type='text' name='title' placeholder='비우면 AI가 자동 생성'>
      <label>대표 이미지 첨부 (선택)</label>
      <input type='file' name='image' accept='image/*'>
      <small class='hint'>첨부하면 자동 생성 대신 이 이미지를 사용합니다.</small>
      <label class='switch' style='margin-top:16px'>
        <input type='checkbox' name='ignore_limit' style='width:auto' checked> 하루 발행 제한 무시</label>
      <label class='switch'>
        <input type='checkbox' name='no_push' style='width:auto'> 테스트만 (GitHub 발행 안 함)</label>
      <button class='btn' type='submit'>글 생성 & 발행 ▶</button>
    </form></div>
    """
    return render("새 글", "new", body)


@app.route("/publish", methods=["POST"])
def publish():
    if _run_state["running"]:
        return render("새 글", "new", "<div class='card'>이미 발행이 진행 중입니다. 로그를 확인하세요.</div>",
                      flash="이미 실행 중입니다.", flash_err=True)

    mode = request.form.get("mode")
    args = [PYTHON, "autoblogger.py"]

    if mode == "keyword":
        keyword = (request.form.get("keyword") or "").strip()
        if not keyword:
            return redirect(url_for("new_post"))
        args += ["--keyword", keyword]
        title = (request.form.get("title") or "").strip()
        if title:
            args += ["--title", title]
        if request.form.get("ignore_limit"):
            args.append("--ignore-daily-limit")
        if request.form.get("no_push"):
            args.append("--no-push")
        # 이미지 업로드 처리
        f = request.files.get("image")
        if f and f.filename:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
            dest = os.path.join(UPLOAD_DIR, f"up_{int(time.time())}{ext}")
            f.save(dest)
            args += ["--image", dest]
    else:  # auto
        source = request.form.get("source", "trends")
        args += ["--source", source]

    run_publish(args)
    return redirect(url_for("logs"))


# ==========================================
# 스케줄 (크론 관리)
# ==========================================

@app.route("/schedule")
def schedule():
    scheds = parse_blog_schedules()
    rows = ""
    for s in scheds:
        label = "방송 건강·식품" if s["source"] == "tv" else "실시간 트렌드"
        hh = s["hour"].zfill(2) if s["hour"].isdigit() else s["hour"]
        mm = s["minute"].zfill(2) if s["minute"].isdigit() else s["minute"]
        state = "⏸ 중지됨" if s["disabled"] else "🟢 활성"
        rows += (
            f"<div class='post'><div style='flex:1'>"
            f"<div class='t'>{hh}:{mm} · {label}</div>"
            f"<div class='muted'>{state}</div></div>"
            f"<form method='post' action='/schedule/remove' style='flex:0'>"
            f"<input type='hidden' name='raw' value=\"{s['raw']}\">"
            f"<button class='btn sm red' type='submit'>삭제</button></form></div>"
        )
    if not rows:
        rows = "<div class='muted'>등록된 자동 스케줄이 없습니다.</div>"

    body = f"""
    <div class='card'><h2>⏰ 자동 발행 스케줄</h2>{rows}</div>
    <div class='card'><h2>스케줄 추가</h2>
    <form method='post' action='/schedule/add'>
      <label>발행 시각</label>
      <input type='time' name='at' value='08:00' required>
      <label>키워드 소스</label>
      <select name='source'>
        <option value='trends'>실시간 트렌드</option>
        <option value='tv'>방송 건강·식품</option>
      </select>
      <button class='btn' type='submit'>스케줄 추가 +</button>
      <small class='hint'>매일 지정한 시각에 자동 발행됩니다. (방송 소재는 밤 시간 권장)</small>
    </form></div>
    <div class='card'><h2>ℹ️ 참고</h2>
    <div class='muted'>스케줄이 실제로 실행되려면 Termux에서 <b>crond</b>가 켜져 있어야 하고,
    안드로이드 배터리 최적화에서 Termux를 제외해야 합니다.</div></div>
    """
    return render("스케줄", "schedule", body)


@app.route("/schedule/add", methods=["POST"])
def schedule_add():
    at = request.form.get("at", "08:00")
    source = request.form.get("source", "trends")
    try:
        hour, minute = at.split(":")
        add_schedule(str(int(hour)), str(int(minute)), source)
        return render("스케줄", "schedule",
                      "<div class='card'>추가했습니다. 목록을 확인하세요.</div>",
                      flash="스케줄을 추가했습니다.")
    except Exception as e:
        return render("스케줄", "schedule", "<div class='card'>실패</div>",
                      flash=f"추가 실패: {e}", flash_err=True)


@app.route("/schedule/remove", methods=["POST"])
def schedule_remove():
    remove_schedule(request.form.get("raw", ""))
    return redirect(url_for("schedule"))


# ==========================================
# 설정 (config.json + .env + git)
# ==========================================

@app.route("/settings")
def settings():
    cfg = load_config()
    env = load_env()
    g = lambda k, d="": cfg.get(k, d)
    body = f"""
    <div class='card'><h2>⚙️ 블로그 설정</h2>
    <form method='post' action='/settings/save'>
      <label>블로그 이름</label>
      <input type='text' name='blog_name' value="{g('blog_name')}">
      <label>블로그 도메인</label>
      <input type='text' name='blog_domain' value="{g('blog_domain')}">
      <label>문의 이메일</label>
      <input type='text' name='contact_email' value="{g('contact_email')}">
      <label>애드센스 client (ca-pub-...)</label>
      <input type='text' name='adsense_client' value="{g('adsense_client')}">
      <label>하루 최대 발행 수</label>
      <input type='number' name='max_posts_per_day' value="{g('max_posts_per_day', 3)}">
      <label>주요 독자층 (비우면 일반 독자)</label>
      <input type='text' name='target_audience' value="{g('target_audience')}" placeholder='예: 3040 직장인 / 비우면 일반'>
      <small class='hint'>글에 특정 표현을 반복하지 않고 눈높이만 맞춥니다.</small>
      <label>주제 분야 (비우면 종합)</label>
      <input type='text' name='topic_focus' value="{g('topic_focus')}" placeholder='예: 육아, 반려동물, 재테크'>
      <label>기본 키워드 소스</label>
      <select name='keyword_source'>
        <option value='trends' {'selected' if g('keyword_source')=='trends' else ''}>실시간 트렌드</option>
        <option value='tv' {'selected' if g('keyword_source')=='tv' else ''}>방송 건강·식품</option>
      </select>
      <label>이미지 모드</label>
      <select name='image_mode'>
        <option value='ai' {'selected' if g('image_mode')=='ai' else ''}>AI 생성 포함</option>
        <option value='free' {'selected' if g('image_mode')=='free' else ''}>무료 소스만</option>
      </select>
      <button class='btn' type='submit'>블로그 설정 저장</button>
    </form></div>

    <div class='card'><h2>🔑 비밀 키 (.env)</h2>
    <form method='post' action='/settings/env'>
      <label>Gemini API 키</label>
      <input type='text' name='GEMINI_API_KEY' value="{env.get('GEMINI_API_KEY','')}" placeholder='AIza...'>
      <label>Unsplash 키 (선택)</label>
      <input type='text' name='UNSPLASH_ACCESS_KEY' value="{env.get('UNSPLASH_ACCESS_KEY','')}">
      <button class='btn' type='submit'>키 저장</button>
      <small class='hint'>이 값들은 .env에만 저장되며 GitHub에 올라가지 않습니다.</small>
    </form></div>

    <div class='card'><h2>📦 저장소 (Git)</h2>
    <form method='post' action='/settings/git'>
      <label>원격 저장소 주소 (origin)</label>
      <input type='text' name='remote' value="{git_remote_url()}">
      <label>배포 브랜치</label>
      <input type='text' name='git_branch' value="{g('git_branch','main')}">
      <button class='btn' type='submit'>저장소 설정 저장</button>
    </form></div>

    <div class='card'><h2>🔒 패널 비밀번호</h2>
    <form method='post' action='/settings/pw'>
      <label>새 비밀번호</label>
      <input type='password' name='webui_password' placeholder='변경하려면 입력'>
      <button class='btn' type='submit'>비밀번호 변경</button>
    </form>
    <a class='btn gray' href='/logout' style='margin-top:10px'>로그아웃</a></div>
    """
    return render("설정", "settings", body)


@app.route("/settings/save", methods=["POST"])
def settings_save():
    cfg = load_config()
    for k in ("blog_name", "blog_domain", "contact_email", "adsense_client",
              "keyword_source", "image_mode", "target_audience", "topic_focus"):
        cfg[k] = request.form.get(k, cfg.get(k, ""))
    try:
        cfg["max_posts_per_day"] = int(request.form.get("max_posts_per_day", 3))
    except ValueError:
        pass
    save_config(cfg)
    return render("설정", "settings", "<div class='card'>저장되었습니다.</div>",
                  flash="블로그 설정을 저장했습니다.")


@app.route("/settings/env", methods=["POST"])
def settings_env():
    env = load_env()
    for k in ("GEMINI_API_KEY", "UNSPLASH_ACCESS_KEY"):
        v = request.form.get(k, "").strip()
        if v:
            env[k] = v
        elif k in env and not v:
            env[k] = ""
    save_env(env)
    return render("설정", "settings", "<div class='card'>키를 저장했습니다.</div>",
                  flash="비밀 키를 저장했습니다.")


@app.route("/settings/git", methods=["POST"])
def settings_git():
    remote = request.form.get("remote", "").strip()
    if remote:
        set_git_remote_url(remote)
    cfg = load_config()
    cfg["git_branch"] = request.form.get("git_branch", "main").strip() or "main"
    save_config(cfg)
    return render("설정", "settings", "<div class='card'>저장소 설정을 저장했습니다.</div>",
                  flash="저장소 설정을 저장했습니다.")


@app.route("/settings/pw", methods=["POST"])
def settings_pw():
    pw = request.form.get("webui_password", "").strip()
    if pw:
        cfg = load_config()
        cfg["webui_password"] = pw
        save_config(cfg)
        return render("설정", "settings", "<div class='card'>비밀번호를 변경했습니다.</div>",
                      flash="비밀번호를 변경했습니다.")
    return redirect(url_for("settings"))


# ==========================================
# 로그
# ==========================================

@app.route("/logs")
def logs():
    body = (
        "<div class='card'><h2>📋 발행 로그</h2>"
        "<div class='muted' id='st'>상태 확인 중...</div>"
        "<pre id='log'>불러오는 중...</pre>"
        "<a class='btn gray' href='/logs'>새로고침</a></div>"
        "<script>"
        "function upd(){fetch('/status').then(r=>r.json()).then(d=>{"
        "document.getElementById('st').innerText=d.running?'🟢 발행 진행 중...':'⚪ 대기 중';"
        "document.getElementById('log').innerText=d.log;"
        "var l=document.getElementById('log');l.scrollTop=l.scrollHeight;"
        "if(d.running)setTimeout(upd,2000);});}upd();"
        "</script>"
    )
    return render("로그", "logs", body)


@app.route("/status")
def status():
    return jsonify(running=_run_state["running"], log=read_run_log())


# ==========================================
# 시작
# ==========================================

_TEMP_PASSWORD = None


def main():
    global _TEMP_PASSWORD
    # 고정 비밀번호가 없으면 임시 비밀번호 생성
    if not (os.environ.get("WEBUI_PASSWORD") or load_config().get("webui_password")):
        _TEMP_PASSWORD = secrets.token_urlsafe(6)
        print("=" * 46)
        print("  최초 로그인 임시 비밀번호:", _TEMP_PASSWORD)
        print("  (설정 화면에서 고정 비밀번호로 바꾸세요)")
        print("=" * 46)

    app.permanent_session_lifetime = datetime.timedelta(days=30)
    host = os.environ.get("WEBUI_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBUI_PORT", "8080"))
    print(f"🌐 컨트롤 패널: http://localhost:{port}  (같은 WiFi의 다른 기기는 http://<폰IP>:{port})")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()

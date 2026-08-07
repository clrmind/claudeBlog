#!/usr/bin/env bash
# =============================================================================
# AutoBlogger(claudeBlog) 서버 설치 스크립트  —  Vultr Ubuntu 24.04
# -----------------------------------------------------------------------------
# 기존 Termux(폰)에서 돌리던 자동블로그를 서버로 옮긴다.
#   - webui.py         : 폰 브라우저로 접속하는 컨트롤 패널 (systemd 서비스로 상주)
#   - autoblogger.py   : 실제 글 생성+GitHub Pages 배포 (webui가 crontab에 스케줄 등록)
#
# 서버에 root로 SSH 접속한 뒤 한 번만 실행:
#   ssh root@158.247.239.7
#   curl -fsSL https://raw.githubusercontent.com/clrmind/claudeBlog/main/deploy/setup_server.sh | bash
# (또는 이 파일을 서버에 올려 `bash setup_server.sh`)
#
# 멱등(idempotent): 다시 실행해도 안전하며, 이미 설정된 항목은 건너뛴다.
# =============================================================================
set -euo pipefail

APP_USER="${APP_USER:-medi}"                       # medi-saas와 같은 계정 재사용
APP_DIR="/home/${APP_USER}/claudeBlog"
REPO="https://github.com/clrmind/claudeBlog.git"
BRANCH="main"                                      # autoblogger가 글을 push하는 브랜치
PORT="${WEBUI_PORT:-8091}"                          # medi-saas(8090)와 겹치지 않게
PY="${APP_DIR}/venv/bin/python"

echo "==> 1/7  시스템 패키지 설치 (python venv / git / cron)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -qq
apt-get install -y -qq python3-venv python3-pip git cron
systemctl enable --now cron            # 스케줄이 실제로 돌려면 cron 데몬이 켜져 있어야 함

echo "==> 2/7  저장소 클론 (${APP_DIR})"
if [ ! -d "${APP_DIR}/.git" ]; then
  sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO}" "${APP_DIR}"
else
  echo "    이미 존재 — 최신으로 갱신"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch origin "${BRANCH}"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" checkout "${BRANCH}"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" pull --rebase origin "${BRANCH}" || \
    sudo -u "${APP_USER}" git -C "${APP_DIR}" rebase --abort || true
fi

echo "==> 3/7  파이썬 가상환경 + 의존성 (flask / requests / pillow)"
if [ ! -x "${PY}" ]; then
  sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/venv"
fi
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -q --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/venv/bin/pip" install -q flask requests pillow

echo "==> 4/7  .env (GEMINI_API_KEY)"
if [ ! -f "${APP_DIR}/.env" ]; then
  read -rp "    Gemini API 키를 붙여넣으세요 (AQ. 또는 AIza 로 시작): " GKEY
  sudo -u "${APP_USER}" bash -c "printf 'GEMINI_API_KEY=%s\n' '${GKEY}' > '${APP_DIR}/.env'"
  chmod 600 "${APP_DIR}/.env"
  echo "    .env 생성 완료"
else
  echo "    이미 존재 — 건너뜀 (수정하려면 ${APP_DIR}/.env 편집)"
fi

echo "==> 5/7  git 신원 + GitHub 푸시 인증(토큰)"
sudo -u "${APP_USER}" git -C "${APP_DIR}" config user.name  "ZionLabs AutoBlogger"
sudo -u "${APP_USER}" git -C "${APP_DIR}" config user.email "contact@zionlabs.org"
CRED_FILE="/home/${APP_USER}/.git-credentials"
if [ ! -s "${CRED_FILE}" ]; then
  echo "    autoblogger가 GitHub(main)로 글을 push하려면 Personal Access Token이 필요합니다."
  echo "    (github.com > Settings > Developer settings > Tokens, repo/contents write 권한)"
  read -rp "    GitHub 사용자명 [clrmind]: " GHUSER
  GHUSER="${GHUSER:-clrmind}"
  read -rsp "    GitHub Token 붙여넣기: " GHTOKEN; echo
  sudo -u "${APP_USER}" git config --global credential.helper store
  sudo -u "${APP_USER}" bash -c "printf 'https://%s:%s@github.com\n' '${GHUSER}' '${GHTOKEN}' > '${CRED_FILE}'"
  chmod 600 "${CRED_FILE}"
  echo "    토큰 저장 완료 (${CRED_FILE}, 600 권한)"
else
  echo "    이미 저장된 자격증명 있음 — 건너뜀"
fi

echo "==> 6/7  webui 컨트롤 패널을 systemd 서비스로 등록 (포트 ${PORT})"
cat >/etc/systemd/system/autoblog-webui.service <<EOF
[Unit]
Description=AutoBlogger web control panel (claudeBlog)
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=WEBUI_HOST=127.0.0.1
Environment=WEBUI_PORT=${PORT}
ExecStart=${PY} webui.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now autoblog-webui
sleep 1
systemctl --no-pager --lines=0 status autoblog-webui || true

echo "==> 7/7  완료"
cat <<EOF

────────────────────────────────────────────────────────────────────────────
 설치 완료.  컨트롤 패널: http://127.0.0.1:${PORT}  (서버 로컬)
 외부(폰)에서 접속하려면 다음 중 하나:
   (A) 임시 확인용 SSH 터널:
       ssh -L ${PORT}:127.0.0.1:${PORT} root@158.247.239.7
       → 폰/PC 브라우저에서 http://localhost:${PORT}
   (B) 상시 도메인(권장): deploy/nginx-autoblog.conf 참고해서
       autoblog.zionlabs.org 서브도메인 + HTTPS 연결

 컨트롤 패널 로그인 비밀번호: config.json 의 "webui_password" 값
 첫 발행 테스트(수동):
   sudo -u ${APP_USER} bash -c 'cd ${APP_DIR} && ./venv/bin/python autoblogger.py --no-push'
 서비스 로그:   journalctl -u autoblog-webui -f
 스케줄 확인:   sudo -u ${APP_USER} crontab -l
────────────────────────────────────────────────────────────────────────────
EOF

#!/data/data/com.termux/files/usr/bin/bash
# 웹 컨트롤 패널 실행 스크립트
# 폰 브라우저에서 http://localhost:8080 접속
cd "$(dirname "$0")"
termux-wake-lock 2>/dev/null
python webui.py

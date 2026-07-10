#!/data/data/com.termux/files/usr/bin/bash
# Termux 스케줄러에서 호출하는 실행 스크립트
cd "$(dirname "$0")"
mkdir -p logs
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 실행 시작 =====" >> logs/autoblogger.log
python autoblogger.py >> logs/autoblogger.log 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 실행 종료 =====" >> logs/autoblogger.log

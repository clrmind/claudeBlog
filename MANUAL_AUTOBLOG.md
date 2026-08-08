# 오토블로그 운영 매뉴얼 (ZionLabs Trend Insights)

실시간 트렌드를 수집해 AI가 칼럼을 쓰고, 정적 사이트로 빌드해 **GitHub → 웹사이트**로
자동 발행하는 시스템의 운영 매뉴얼입니다. 폰(Termux) 대신 **Vultr 서버에서 24시간 자동**으로 돕니다.

> 이 문서의 `<서버IP>`, `<패널비밀번호>` 등 꺾쇠 표시는 실제 값으로 바꿔 읽으세요.
> 실제 값(IP·비밀번호·토큰)은 저장소에 적지 않습니다.

---

## 1. 전체 구조 한눈에

```
[서버 cron]  매일 10:30 / 15:00 / 22:30 (KST)
     │
     ▼
autoblogger.py  ──①트렌드 수집 → ②Gemini가 소재 선정 → ③AI 칼럼 작성 →
     │             ④정적 사이트 빌드 → ⑤GitHub main 브랜치로 자동 push
     ▼
GitHub 저장소(main)  ──▶  GitHub Pages 자동 빌드  ──▶  blog.zionlabs.org
                                                    (DNS CNAME → clrmind.github.io)

[webui.py]  컨트롤 패널(포트 8091, 상시 서비스) — 수동 발행·설정·스케줄·로그를 폰/PC로 관리
```

- **블로그 본체는 GitHub Pages가 호스팅** — 서버는 "글을 만들어 GitHub에 올리는 일"과 "컨트롤 패널"만 담당
- medi-saas(오토포스트 Pro, 포트 8090)와 **포트·폴더가 겹치지 않아** 한 서버에서 공존

---

## 2. 서버 구성

| 항목 | 값 |
|---|---|
| 접속 | `ssh root@<서버IP>` |
| 앱 폴더 | `/home/medi/claudeBlog` |
| 실행 계정 | `medi` |
| 파이썬 | `/home/medi/claudeBlog/venv/bin/python` |
| 컨트롤 패널 서비스 | `autoblog-webui` (systemd, 포트 8091, `127.0.0.1`에만 바인딩) |
| 자동 발행 | `medi` 계정 crontab |
| 발행 로그 | `/home/medi/claudeBlog/auto_run.log` |

---

## 3. 컨트롤 패널(webui) 사용법

패널은 보안을 위해 서버 내부(`127.0.0.1:8091`)에만 열려 있습니다. **SSH 터널**로 접속합니다.

```bash
# PC/폰 터미널에서
ssh -L 8091:127.0.0.1:8091 root@<서버IP>
```
접속을 유지한 채 브라우저에서 **`http://localhost:8091`** → 비밀번호 `<패널비밀번호>` 로 로그인.

패널에서 할 수 있는 것:
- **수동 발행**: 키워드를 직접 넣거나 자동 선정으로 즉시 1편 발행
- **이미지/제목/키워드 직접 지정**: 대표 이미지 첨부, 제목·키워드 수동 입력
- **설정**: 블로그 이름·설명, 타깃 독자, 소재 방향 등(config.json 편집)
- **⏰스케줄**: 자동 발행 시각 추가/삭제 (서버 crontab에 직접 반영됨)
- **로그**: 최근 실행 로그 확인

---

## 4. 자동 발행 스케줄

현재 스케줄: **매일 10:30 / 15:00 / 22:30 (KST), 하루 3편**.

- 스케줄은 패널 **⏰스케줄** 탭에서 관리(권장). 또는 서버에서 직접:
  ```bash
  sudo -u medi crontab -l          # 현재 스케줄 확인
  ```
- **시간대는 반드시 KST 여야** 합니다. 확인:
  ```bash
  timedatectl        # Time zone: Asia/Seoul (KST, +0900) 이면 정상
  ```
  UTC로 나오면: `sudo timedatectl set-timezone Asia/Seoul && sudo systemctl restart cron`
- 하루 발행 상한은 `config.json`의 `max_posts_per_day`(기본 3). 스팸성 대량 발행을 막아 애드센스 정책을 보호합니다.
- 소재 방향은 스케줄 줄의 명령에 `--source tv`(방송 건강·식품) 또는 `--source trends`(실시간 트렌드, 기본)로 지정.

---

## 5. 설정(config.json) 주요 항목

| 키 | 의미 |
|---|---|
| `blog_name` / `blog_description` | 블로그 제목·설명 |
| `blog_domain` | 사이트 주소(canonical·CNAME 파생) |
| `model_name` | 글 생성 모델. **`gemini-flash-latest`** 권장(모델 폐기로 멈추는 것 방지) |
| `image_model` | 이미지 생성 모델(`gemini-2.5-flash-image`) |
| `image_mode` | `ai`(AI 생성) / 기타 |
| `max_posts_per_day` | 하루 발행 상한 |
| `keyword_source` | 기본 소재(`trends` / `tv`) |
| `posts_per_page` | 목록 페이지당 글 수 |
| `target_audience` / `topic_focus` | 타깃 독자·소재 방향(비우면 기본 50대 트렌드) |

> `webui_password`는 **config.json에 두지 않습니다**(저장소 공개 시 노출). 서버의 systemd 환경변수
> `WEBUI_PASSWORD`로 관리합니다(§8 참고).

---

## 6. 배포 구조와 도메인 (중요 — 과거 장애 원인)

- autoblogger가 GitHub `main`에 push → **GitHub Pages**가 자동 빌드 → `blog.zionlabs.org`.
- DNS: Cloudflare에서 `blog` CNAME → **`clrmind.github.io`**, **프록시 "DNS 전용(회색 구름)"**.
  - ⚠️ 프록시(주황 구름)를 켜면 GitHub이 HTTPS 인증서를 못 잡고 캐시 문제가 생깁니다. **회색 유지**.
  - ⚠️ 과거 장애: `blog`가 GitHub이 아닌 **Cloudflare Pages(`zionlabs.pages.dev`)** 를 가리켜, GitHub에
    아무리 올려도 사이트가 안 바뀌었습니다. 대상이 **`clrmind.github.io`** 인지 항상 확인하세요.
- 저장소는 **public** 이어야 GitHub Pages가 무료로 동작합니다(private면 Pro 필요).
- HTTPS: GitHub → **Settings → Pages → Enforce HTTPS** 체크(인증서 발급 후 활성화됨).

---

## 7. 자주 쓰는 점검·운영 명령

```bash
# 지금 즉시 1편 발행(테스트, push까지)
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py'
# 생성만 하고 push 안 함
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py --no-push'
# 글 없이 사이트만 재빌드
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py --render-only'

sudo systemctl status autoblog-webui     # 패널 서비스 상태
journalctl -u autoblog-webui -f          # 패널 로그
tail -f /home/medi/claudeBlog/auto_run.log   # 자동 발행 로그
sudo -u medi crontab -l                  # 스케줄 확인

# 사이트가 최신인지(원본이 새 글을 담고 있는지) 서버에서 확인
curl -s https://blog.zionlabs.org/ | grep -o 'post_[0-9_]*' | head
```

---

## 8. 비밀번호·키 변경

**패널 비밀번호** (webui 메뉴가 아니라 systemd 환경변수로 관리):
```bash
sudo sed -i 's/^Environment=WEBUI_PASSWORD=.*/Environment=WEBUI_PASSWORD=새비밀번호/' \
  /etc/systemd/system/autoblog-webui.service
sudo systemctl daemon-reload && sudo systemctl restart autoblog-webui
```

**Gemini API 키**: `/home/medi/claudeBlog/.env` 의 `GEMINI_API_KEY=...` 수정 후 필요 시 서비스 재시작.

**GitHub 푸시 토큰**: `origin` 원격 URL 또는 `/home/medi/.git-credentials` 에 저장됨. 만료 시 새 토큰으로 교체.

---

## 9. 문제 해결

| 증상 | 원인 / 해결 |
|---|---|
| 발행 시 **"데모 모드"** 또는 **HTTP 404 (모델)** | `.env`의 `GEMINI_API_KEY` 확인. 모델 폐기면 `config.json`의 `model_name`을 `gemini-flash-latest`로 |
| **push 실패(인증)** | 토큰 만료/권한(Contents read·write). `sudo -u medi git -C /home/medi/claudeBlog push`로 직접 테스트 |
| **글은 올라갔는데 사이트 반영 안 됨** | ①GitHub Actions에 "pages build and deployment" 성공했는지 ②DNS `blog` 대상이 `clrmind.github.io`인지 ③Cloudflare 프록시 회색인지 (§6) |
| **HTTPS 자물쇠 안 됨** | DNS 회색 유지 후 몇 분~1시간 뒤 Settings→Pages에서 Enforce HTTPS 체크 |
| **스케줄이 안 돎** | `systemctl status cron` active인지, `crontab -l`에 줄이 있는지, 시간대가 KST인지 |

---

## 10. 코드 갱신 / 재배포

```bash
# 최신 코드로 갱신 + 서비스 재시작
sudo -u medi git -C /home/medi/claudeBlog pull --rebase origin main
sudo -u medi /home/medi/claudeBlog/venv/bin/pip install -q flask requests pillow
sudo systemctl restart autoblog-webui
```
설치 스크립트 `deploy/setup_server.sh`를 다시 실행해도 안전하게 갱신됩니다(멱등).

---

### 한 줄 요약
서버 cron이 하루 3번 자동으로 글을 만들어 GitHub에 올리고, GitHub Pages가 `blog.zionlabs.org`에
자동 반영합니다. 관리는 SSH 터널 → `http://localhost:8091` 패널에서. 사이트가 안 바뀌면 **DNS 대상이
`clrmind.github.io`인지**(§6)부터 확인하세요.

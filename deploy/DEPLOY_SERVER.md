# 자동블로그(claudeBlog)를 Vultr 서버에서 실행하기

폰(Termux)에서 돌리던 자동블로그를 **Vultr 서버(158.247.239.7)** 로 옮겨,
폰을 켜두지 않아도 서버가 알아서 매일 글을 발행하도록 한다.

## 구조

| 구성요소 | 역할 | 서버에서의 형태 |
|---|---|---|
| `autoblogger.py` | 트렌드 수집 → Gemini 글 생성 → 정적사이트 빌드 → **GitHub `main`에 push** → GitHub Pages(`blog.zionlabs.org`)가 자동 반영 | cron이 정해진 시간에 실행 |
| `webui.py` | 폰 브라우저용 컨트롤 패널(수동 발행·설정·**스케줄 관리**·로그) | `autoblog-webui` systemd 서비스로 상시 실행 (포트 8091) |

> 스케줄은 webui 패널의 **⏰스케줄** 탭에서 등록/삭제한다. webui가 `medi` 계정의
> crontab에 `autoblogger.py` 실행 줄을 직접 써 넣고, 서버의 cron 데몬이 그 시간에 실행한다.
> (Termux에서 crond를 켜두던 것과 동일한 방식 — 서버에선 cron이 항상 켜져 있으니 폰이 꺼져도 됨.)

블로그 본체는 **GitHub Pages가 호스팅**하므로 서버가 웹을 직접 서빙하지 않는다.
서버는 "글을 만들어 GitHub에 올리는 일"과 "컨트롤 패널"만 담당한다.
medi-saas(오토포스트 Pro, 포트 8090)와 **포트/디렉터리가 겹치지 않아** 한 서버에서 공존한다.

## 설치 (서버에 SSH 접속 후 한 번만)

```bash
ssh root@158.247.239.7
curl -fsSL https://raw.githubusercontent.com/clrmind/claudeBlog/main/deploy/setup_server.sh | bash
```

스크립트가 순서대로 물어본다:
1. **Gemini API 키** — `.env`에 저장 (medi-saas와 같은 키 재사용 가능)
2. **GitHub Token** — autoblogger가 `main`에 push하려면 필요.
   `github.com > Settings > Developer settings > Personal access tokens`,
   `repo`(또는 contents read/write) 권한. 이전에 medi 배포 때 만든 토큰 재사용 가능.

끝나면 webui가 `autoblog-webui` 서비스로 상주하기 시작한다.

## 컨트롤 패널 접속

블로그 관리 패널은 보안을 위해 외부에 바로 열지 않고 `127.0.0.1:8091`에만 뜬다. 접속 방법 2가지:

**(A) 간단 — SSH 터널** (가끔 관리할 때)
```bash
ssh -L 8091:127.0.0.1:8091 root@158.247.239.7
```
접속 유지한 채 폰/PC 브라우저에서 `http://localhost:8091`.

**(B) 권장 — 상시 도메인** (`autoblog.zionlabs.org`)
```bash
# DNS: autoblog.zionlabs.org (A) → 158.247.239.7
sudo cp /home/medi/claudeBlog/deploy/nginx-autoblog.conf /etc/nginx/sites-available/autoblog
sudo ln -s /etc/nginx/sites-available/autoblog /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d autoblog.zionlabs.org
```
이후 폰에서 `https://autoblog.zionlabs.org`.

**로그인 비밀번호**: `config.json`의 `webui_password` 값.

## 스케줄 걸기 (자동 발행 시작)

1. 컨트롤 패널 접속 → **⏰스케줄** 탭
2. 시각과 소재(`trends` 실시간 트렌드 / `tv` 방송 건강·식품)를 골라 추가
3. 이제 서버 cron이 매일 그 시각에 자동 발행 → GitHub Pages 자동 갱신

하루 발행량은 `config.json`의 `max_posts_per_day`(기본 3)로 제한된다(애드센스 정책 보호).

## 확인·운영 명령

```bash
# 수동으로 글 1개 발행 테스트 (push까지)
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py'
# push 없이 생성만 테스트
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py --no-push'

sudo systemctl status autoblog-webui     # 패널 상태
journalctl -u autoblog-webui -f          # 패널 로그
sudo -u medi crontab -l                  # 등록된 스케줄
tail -f /home/medi/claudeBlog/auto_run.log   # 자동 발행 로그
```

재배포(코드 갱신): `setup_server.sh`를 다시 실행하면 최신 코드로 갱신되고 서비스가 재시작된다.

## 문제 해결

- **패널에서 발행했는데 "데모 모드"/404 모델 오류** → `.env`의 `GEMINI_API_KEY` 확인.
  모델 폐기(`gemini-2.5-flash` 404) 시 `config.json`의 `model_name`을
  `gemini-flash-latest`(항상 최신 flash 별칭)로 바꾸면 해결된다.
- **push 실패(인증)** → `/home/medi/.git-credentials`의 토큰 만료/권한 확인.
  `sudo -u medi git -C /home/medi/claudeBlog push`로 직접 테스트.
- **스케줄이 안 도는 듯** → `systemctl status cron` 이 active인지, `crontab -l`에 줄이 있는지 확인.

# 자동블로그(claudeBlog) 운영·안정화 문서

`blog.zionlabs.org` 자동블로그의 **AI 생성 복원력 · 장애 대응 · 자동 모니터링**을 정리한 문서.
서비스 구조·배포·스케줄 등 기본 운영은 [`MANUAL_AUTOBLOG.md`](./MANUAL_AUTOBLOG.md)를 먼저 참고.

> 대상 서버: `/home/medi/claudeBlog` (실행 계정 `medi`) · 파이썬 `venv/bin/python`
> 발행 결과는 GitHub `main` push → GitHub Pages가 `blog.zionlabs.org`에 자동 반영.

---

## 1. 한눈에 보는 현재 구성

| 구성 | 값 |
|---|---|
| 글 생성 엔진 | `autoblogger.py` (Google Gemini API) |
| 기본 모델 | `config.json`의 `model_name` = **`gemini-flash-lite-latest`** |
| 발행 스케줄(cron) | 매일 **10:30 / 15:00 / 22:30 (KST)**, `CRON_TZ=Asia/Seoul` |
| 헬스체크(cron) | 매일 **23:40 (KST)** `monitor.py` |
| 자동 알림 | **ntfy**(폰 푸시). 토픽은 `.env`의 `NTFY_TOPIC` |
| 배포 | `sudo -u medi git -C /home/medi/claudeBlog pull origin main` |

---

## 2. AI 생성 복원력 (핵심)

### 왜 필요한가
Google의 모델 별칭 `gemini-flash-latest`는 인기가 높아 **429(속도제한)/503(과부하)** 를 자주 반환한다.
과거에는 이 모델 하나만 3회 재시도했기 때문에, 붐비면 **그날 발행이 통째로 실패**했다.

### 지금 동작 방식 (`autoblogger.py`의 `call_gemini_json`)
1. **런타임 자동탐색** — `discover_models()`가 이 API 키로 `generateContent` 가능한
   실제 모델 목록을 조회(1회 캐시). 발행 로그에 `🔎 이 키로 사용 가능한 텍스트 모델 …` 로 남는다.
2. **폴백 체인** — `text_model_chain()`이 `[기본모델] + flash → 기타 → pro → 하드코딩후보`
   순서로 시도 목록을 만든다. 이미지·TTS·로보틱스 등 **텍스트 생성용이 아닌 모델은 제외**(`_NON_TEXT_HINTS`).
3. **재시도·전환 규칙**
   - `429/500/502/503/504` → **지수 백오프(4·8·16·32초, 최대 4회)** 후 재시도
   - 재시도 소진 → **다음 모델로 폴백** (`↪️ … 다음 모델로 폴백`)
   - `400/404`(모델 폐기 등) → 재시도 없이 **즉시 다음 모델로** (`⚠️ … 사용 불가`)
   - 성공 → `✅ 폴백 모델 '…'로 생성 성공` (기본모델이 아니었을 때만 로그)

즉 **어떤 모델이 붐비거나 폐기돼도 자동으로 살아있는 모델로 갈아탄다.**
모델 이름이 바뀌는 정도는 사람이 손댈 필요가 없다.

### 모델 참고 (2026-08 기준, 이 키에서 확인)
- **작동**: `gemini-flash-lite-latest`(기본), `gemini-flash-latest`(자주 과부하)
- **폐기/미지원(404)**: `gemini-2.5-flash`, `gemini-2.0-flash` 등 구버전
- 더 긴 글이 필요하면 `config.json`의 `model_name`을 `gemini-3.5-flash` 등으로 바꿀 수 있다
  (실패 시 폴백이 받아줌). `.env`에는 이 서비스에서 모델 override 키를 쓰지 않는다(오토포스트 Pro는 `GEMINI_MODEL` 사용).

---

## 3. 2026-08 장애 사례 (포스트모템)

**증상**: 8/9 이후 약 2주간 blog.zionlabs.org에 새 글이 올라오지 않음.

**원인은 두 가지였다 (503 하나가 아님):**

1. **push 실패로 글 23편이 서버 로컬에만 적체**
   - 서버의 로컬 `main`이 원격과 갈라진(diverged) 상태로 남아, 생성된 글이 GitHub에 push되지 않고 쌓임.
   - `git status`가 `ahead 23`으로 나온 것이 결정적 단서였다.
2. **`gemini-flash-latest` 상시 과부하(429/503)**
   - 일부 실행에서 생성 자체가 실패(당시엔 폴백이 없어 그날 발행 실패).

**조치**
- 적체분 복구: `git fetch → git rebase origin/main → git push` 로 23편 + 코드수정을 한 번에 반영.
- 재발 방지: 위 **2. 복원력**(폴백/백오프/자동탐색) 이식 + 기본 모델을 `gemini-flash-lite-latest`로 교체.

**교훈**: "새 글이 안 보임"의 원인은 생성 실패뿐 아니라 **push 실패**일 수 있다.
→ 그래서 아래 모니터링이 "발행 신선도"를 직접 감시한다.

---

## 4. 자동 모니터링 (`monitor.py`)

문제가 있을 때만 폰으로 알린다. 정상이면 조용(매일 수동 점검 불필요).

**점검 항목**
1. **블로그 신선도** — `posts/post_YYYYMMDD_HHMMSS.html` 파일명 기준, 최근 글이
   `HEALTH_STALE_HOURS`(기본 26시간)보다 오래되면 경고. → cron 중단 / 생성 전부 실패 / push 실패를 모두 잡음.
2. **Gemini 접근성** — `GEMINI_API_KEY`로 모델 목록을 조회해 키 만료/쿼터 소진 감지.
   (자동블로그·오토포스트 Pro **공통** 원인)

**알림 채널**: ntfy. `.env`에 아래를 둔다.
```
NTFY_TOPIC=zionlabs-alert-xxxx      # 폰 ntfy 앱에서 이 토픽 구독
# NTFY_URL=https://ntfy.sh          # (선택)
# HEALTH_STALE_HOURS=26             # (선택)
```
> ntfy 토픽은 이름만 알면 누구나 볼 수 있으므로 **추측 불가능한 무작위 문자열**을 쓴다.

**수동 테스트**
```bash
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python monitor.py --test'   # 테스트 푸시 1건
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python monitor.py'           # 실제 점검
```

**cron** (crontab에 등록됨)
```
40 23 * * * cd /home/medi/claudeBlog && ./venv/bin/python monitor.py >> monitor.log 2>&1
```

---

## 5. 운영 체크 명령 모음

```bash
# 스케줄 확인
sudo -u medi crontab -l
# 최근 자동 발행 로그
tail -40 /home/medi/claudeBlog/auto_run.log
# 지금 즉시 1편 발행(테스트, push까지)
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python autoblogger.py'
# 코드 최신화(배포)
sudo -u medi git -C /home/medi/claudeBlog pull origin main
# 이 키로 쓸 수 있는 모델 목록 보기
sudo -u medi bash -c 'cd /home/medi/claudeBlog && ./venv/bin/python -c "import autoblogger as A,requests,os;A.load_env_file();k=os.environ.get(\"GEMINI_API_KEY\");r=requests.get(\"https://generativelanguage.googleapis.com/v1beta/models\",headers={\"x-goog-api-key\":k},timeout=30);print([m[\"name\"].replace(\"models/\",\"\") for m in r.json().get(\"models\",[]) if \"generateContent\" in m.get(\"supportedGenerationMethods\",[])])"'
```

## 6. 문제별 대응 요약

| 증상 | 확인 | 대응 |
|---|---|---|
| 새 글이 안 올라옴 | `git -C … status`가 `ahead N`? | `git fetch && git rebase origin/main && git push` |
| 생성이 계속 실패 | `auto_run.log`에 429/503 반복 | 폴백이 처리함. 전부 실패면 잠시 후 자동 복구 |
| 알림이 안 옴 | `monitor.py --test` | `.env`의 `NTFY_TOPIC` = 폰 앱 구독 토픽 일치 확인 |
| Gemini 키 오류 | monitor 알림 | `.env` `GEMINI_API_KEY` 교체 / 무료쿼터 확인 |
| 사이트만 반영 안 됨 | GitHub Actions "pages build" | DNS `blog`→`clrmind.github.io` (MANUAL §6) |

---

_최종 갱신: 2026-08 · 관리 주체: 주식회사 시온랩스_

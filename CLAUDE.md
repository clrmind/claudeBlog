# 자동블로그 (claudeBlog)

AI가 트렌드를 수집해 글을 쓰고 **정적 사이트로 빌드해 GitHub Pages에 배포**하는 블로그.

- 운영: https://blog.zionlabs.org (GitHub Pages, `main` 브랜치, `CNAME`)
- 관리 패널: https://autoblog.zionlabs.org (`webui.py`, systemd `autoblog-webui`, 포트 8091)
- 서버: Vultr `158.247.239.7`, 앱 경로 `/home/medi/claudeBlog`

## 구성

| 파일 | 역할 |
|---|---|
| `autoblogger.py` | 트렌드 수집 → Gemini 글 생성 → 정적 사이트 빌드 → `main`에 push |
| `webui.py` | 수동 발행·스케줄·설정용 웹 컨트롤 패널 |
| `monitor.py` | 발행이 멈췄는지 감시 |
| `posts/data.json` | **모든 글의 원본 데이터.** 글 하나가 dict 하나 |
| `posts/*.html`, `index*.html`, `tags/`, `rss.xml`, `sitemap.xml` | 전부 빌드 산출물 |

## 가장 중요한 규칙

### `posts/*.html`을 직접 고치지 말 것

이 파일들은 **빌드할 때마다 `posts/data.json`에서 통째로 다시 생성된다.**
HTML을 직접 고치면 다음 빌드에서 소리 없이 사라진다(실제로 겪었다).

글을 고치려면 `posts/data.json`의 해당 항목을 고치고 다시 빌드한다.

```
python3 autoblogger.py --render-only --no-push
```

`data.json`을 쓸 때는 **반드시 `indent=2`, `ensure_ascii=False`** 로 저장할 것.
안 그러면 전체 파일이 한 줄로 바뀌어 diff가 수천 줄이 된다.

```python
json.dump(posts, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
```

## 글 항목 형식

`title`, `meta_description`, `tags`(list), `content`(HTML 문자열), `keyword`,
`filename`(`post_YYYYMMDD_HHMMSS`), `date`(`YYYY-MM-DD`), `image`, `image_credit`,
`image_category`, `person_name`, `image_prompt`, `trend_reason`

- `image`는 보통 `/images/<이름>.svg` (대표 이미지는 SVG로 생성한다)
- `content`는 `<h2>`, `<p>`, `<ul>`, `<figure>`를 쓸 수 있다.
  본문 이미지 스타일은 `autoblogger.py`의 `.article-body img` 규칙이 담당한다

## 사용자가 쓴 원고를 발행하기

```
python3 autoblogger.py --polish-file 원고.txt
```

AI가 제목·태그·SEO를 다듬어 발행하고 원고 파일은 지운다.

## 이미지

- 대표 이미지와 도식은 **SVG로 직접 그린다**(`images/` 에 저장). 벡터라 확대해도 안 깨진다
- **네이버 블로그 이미지 주소는 쓸 수 없다.** 외부 도메인에서 불러오면 차단돼 깨져 보인다.
  파일을 받아 `images/`에 넣어야 한다
- 본문 이미지에는 `width`/`height`를 명시할 것(레이아웃 밀림 방지)

## 검증

`file://`로 열면 `/images/...` 절대경로가 안 잡혀 모든 이미지가 깨진 것처럼 보인다.
반드시 HTTP로 띄워서 확인할 것.

```
python3 -m http.server 8777
```

`loading="lazy"` 때문에 스크롤을 끝까지 내려야 아래쪽 이미지가 로드된다.

## 관리 패널 비밀번호

우선순위: **시스템 환경변수 → `.env` → `config.json` → 임시 비밀번호**

systemd 유닛에 `Environment=WEBUI_PASSWORD=`가 있으면 `.env`를 고쳐도 안 먹는다.
`.env`(`.gitignore` 등록됨, 권한 600)에만 두는 것이 옳다.

평문으로 비교하므로 다른 서비스와 같은 비밀번호를 쓰지 말 것.
예전에 `config.json`에 평문으로 커밋된 이력이 git 히스토리에 남아 있다.

## 원격과 갈라졌을 때

크론이 매일 push 하는데 사람이 GitHub 에 직접 push 하고 서버가 그걸 안 받아오면
갈라진다. 그 뒤로는 크론이 돌 때마다 `git pull --rebase` 가 **생성 파일에서**
충돌한다 — 글 하나를 쓸 때마다 `data.json` 과 빌드된 HTML 이 통째로 바뀌기 때문이다.

예전 코드는 충돌하면 `rebase --abort` 하고 **그대로 push 를 시도**했다. 되돌렸으니
될 리가 없다. 네 번 재시도하고 포기하는데 아무도 모른다 — 실제로 엿새치가 쌓였다.

지금은 `recover_diverged()` 가 스스로 푼다.

- **생성 파일은 충돌을 풀 이유가 없다. 다시 만들면 된다.** 진짜 원본은
  `posts/data.json` 과 `images/` 뿐이므로 그 둘만 합치고 나머지는 재빌드한다
- `data.json` 은 `filename` 기준 합집합이다. **같은 글이 양쪽에 있으면 원격이
  이긴다** — 사람이 손으로 고친 판이 거기 있고 크론은 옛 판을 들고 있다
- 합친 결과가 어느 한쪽보다 **적으면 덮지 않고 멈춘다.** 백업을 남긴 뒤에 한다
- `reset --hard` 가 추적 파일인 이미지를 지우므로, 미리 옮겨 뒀다가
  **원격 것을 덮지 않고** 되살린다

### 손으로 고쳐야 할 때

```
sudo -u medi git -C /home/medi/claudeBlog fetch origin main
sudo -u medi git -C /home/medi/claudeBlog checkout origin/main -- autoblogger.py
sudo -u medi python3 /home/medi/claudeBlog/autoblogger.py --render-only
```

`autoblogger.py` 만 먼저 받아 오는 것이 요령이다. 갈라진 상태에서는 `git pull`
자체가 충돌하지만 `checkout origin/main -- 파일` 은 그 파일만 가져온다.

## 주의

- 서버의 `venv`에는 `requests`가 빠져 있다. 빌드는 시스템 `python3`로 돌아간다
- 크론이 매일 자동 발행·push 하므로, 작업 전 `git pull origin main` 할 것

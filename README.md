# AutoBlogger v2 — 50대 타깃 트렌드 자동 블로그

스마트폰(Termux)에서 스케줄러로 자동 실행되어, **50대 독자에게 인기 있는 실시간 키워드**로
칼럼을 생성하고 GitHub Pages에 자동 배포하는 프로그램입니다.

## 📱 웹 컨트롤 패널 (폰에서 UI로 조작)

명령어 없이 폰 브라우저에서 조작하고 싶으면 웹 패널을 실행하세요. **안드로이드·아이폰 모두** 호환됩니다.

```bash
pip install flask
python webui.py          # 또는 ./run_webui.sh
```
→ 폰 브라우저에서 **http://localhost:8080** 접속 (다른 기기는 같은 WiFi에서 `http://<폰IP>:8080`)

- **홈**: 발행 현황, 빠른 자동 발행, 최근 글
- **새 글**: 키워드 직접 입력 + 제목 지정 + **이미지 직접 첨부** + 발행
- **스케줄**: 자동 발행 시각 추가/삭제 (크론 자동 관리)
- **설정**: 도메인·애드센스·저장소 주소·Gemini/Unsplash 키 등 입력
- **로그**: 발행 진행 상황 실시간 확인

> 최초 실행 시 콘솔에 **임시 비밀번호**가 출력됩니다. 설정 화면에서 고정 비밀번호로 바꾸세요.
> 다른 기기에서 접속하려면 비밀번호를 반드시 설정하세요 (같은 WiFi의 누구나 접근 가능하므로).

## 동작 방식

```
[스케줄러(cron)] → autoblogger.py 실행
  1. 키워드 수집         : (아래 '키워드 소스' 참고)
  2. 키워드 선별 (Gemini): 50대가 가장 클릭할 키워드 1개 선정 (건강/연금/재테크 우선)
  3. 칼럼 생성 (Gemini)  : SEO 제목 + 메타설명 + 2,000자 이상 본문 + FAQ
  4. 사이트 빌드         : index/포스트 HTML, sitemap.xml, rss.xml, robots.txt, ads.txt
  5. GitHub 자동 배포    : commit → pull --rebase → push (재시도 포함)
```

같은 키워드를 반복 발행하지 않도록 최근 100개 발행 이력을 `data/keyword_history.json`에
관리하며, `max_posts_per_day` 설정으로 하루 발행량을 제한합니다.

## 키워드 소스 (`keyword_source` 또는 `--source`)

| 소스 | 설명 | 적합한 블로그 |
|------|------|--------------|
| `trends` (기본) | 구글 트렌드 KR RSS + signal.bz 실검 TOP10 | 종합 정보 블로그 |
| `tv` | **방송 편성표 기반 건강·식품 소재 크롤링** | 건강/식품 특화 블로그 |

### 방송 편성표 소스 (`tv`)

50대 시청층이 두터운 건강·식품 정보 프로그램(생로병사의 비밀, 엄지의 제왕, 알토란,
한국인의 밥상 등)의 **오늘 방송 회차 소재**를 네이버 검색으로 크롤링합니다.
방송 직후 검색량이 폭증하지만 경쟁 글은 적어 유입 효율이 높습니다.

- **저작권 안전장치**: 방송 '내용'을 전재하지 않고 **소재 키워드만** 참고하여,
  Gemini가 이를 방송과 무관한 독립적 정보성 글로 재구성합니다.
  (예: `엄지의 제왕: 혈관 청소 음식` → `혈관에 좋은 음식과 혈관 건강 관리법`)
- **견고성**: 회차 소재 크롤링이 실패해도 프로그램 목록을 맥락으로 넘겨 Gemini가
  건강/식품 주제를 생성하며, 그마저 실패하면 상시 인기 주제로 자동 대체됩니다.
- 대상 프로그램은 `autoblogger.py`의 `TV_HEALTH_FOOD_PROGRAMS`에서 수정할 수 있습니다.

```bash
python autoblogger.py --source tv --no-push   # 방송 소재로 테스트
```

> 💡 방송 시간대(대체로 저녁~밤) 직후에 cron을 걸면 소재 적중률이 가장 높습니다.
> 예: `0 22 * * * ...` (매일 밤 10시, 건강 프로그램 종영 직후)

## 대표 이미지 파이프라인

글마다 아래 순서로 시도하여 **중복 없는 맞춤 이미지**를 자동으로 결정합니다.

| 순서 | 방식 | 설명 |
|------|------|------|
| ① | 위키백과 인물 사진 | 실존 인물 중심의 글이면 위키백과 대표 사진 사용 (자유 라이선스, 출처 자동 표기) |
| ② | **AI 이미지 생성** | Gemini 이미지 모델이 글 내용에 맞는 커버를 생성해 `images/`에 저장 |
| ③ | Unsplash 검색 | `.env`에 `UNSPLASH_ACCESS_KEY`가 있으면 키워드 검색으로 실사진 사용 |
| ④ | 브랜드 커버 카드 | 제목 텍스트 + 카테고리별 그라데이션 SVG 카드 자동 생성 (항상 성공) |

- **비용**: AI 이미지는 1장당 약 $0.04 수준(gemini-2.5-flash-image 기준)으로, 하루 3장이면
  월 $4 내외입니다. 무료로만 운영하려면 `config.json`에서 `"image_mode": "free"`로 바꾸면
  ②를 건너뛰고 ①→③→④ 순서로만 동작합니다.
- **안전장치**: AI 프롬프트에 '실존 인물 얼굴·글자 금지'를 강제하여 딥페이크/워터마크 문제를
  차단하고, 인물 사진은 자유 라이선스인 위키백과만 사용합니다.

## 설치 (Termux)

```bash
pkg update && pkg upgrade
pkg install python git cronie termux-services libjpeg-turbo
pip install requests Pillow   # Pillow는 선택 — AI 이미지를 자동 압축해 저장소 용량 절약

git clone https://github.com/clrmind/claudeblog.git
cd claudeblog
cp .env.example .env
nano .env        # GEMINI_API_KEY 입력 (https://aistudio.google.com 에서 발급)
nano config.json # 도메인, 애드센스 ID 등 수정
chmod +x run_blog.sh
```

### 수동 테스트

```bash
python autoblogger.py --no-push        # 글 생성 + 빌드만 (푸시 안 함)
python autoblogger.py --keyword "갱년기 영양제"  # 키워드 직접 지정
python autoblogger.py --render-only    # 글 생성 없이 사이트만 재빌드
python autoblogger.py                  # 전체 자동 실행
```

### 자동 스케줄링 (하루 3회 예시)

```bash
sv-enable crond       # termux-services로 crond 활성화
crontab -e
```

crontab에 추가:

```
0 8,13,19 * * * /data/data/com.termux/files/home/claudeblog/run_blog.sh
```

> 💡 **폰 설정 필수**: Termux 앱을 배터리 최적화에서 제외하고, Termux 알림에서
> `termux-wake-lock`을 켜두면 백그라운드에서 안정적으로 동작합니다.

## 체류시간·수익 극대화 기능

방문자가 한 페이지만 보고 나가지 않도록(이탈률↓, 페이지뷰↑ = 광고 노출↑) 아래 기능이
모든 글에 자동 적용됩니다.

- **관련도 기반 추천**: 태그·카테고리·제목 유사도를 계산해 진짜 관련 있는 글을 추천
- **본문 중간 내부링크 박스**: 세 번째 소제목 앞에 '함께 읽으면 좋은 글' 삽입 (스크롤 중 이탈 방지)
- **목차(TOC)**: 소제목 3개 이상이면 자동 생성 — 긴 글 가독성 + 체류시간 증가
- **이전/다음 글 내비게이션**: 글 끝에서 자연스럽게 다음 글로 유도
- **태그 허브 페이지** (`/tags/…`): 태그 클릭 시 관련 글 모음으로 이동, 검색엔진 유입 페이지 역할도 겸함
- **글자 크기 조절 버튼(가-/가+)**: 50대 독자 배려 — 설정은 localStorage에 저장되어 유지됨
- **읽기 진행 바**: 상단에 읽은 분량 표시 (완독 유도)
- **도입부 훅**: 첫 문단을 질문/사례로 시작하고 짧은 문단으로 쓰도록 생성 프롬프트에 반영

## 설정 (config.json)

| 항목 | 설명 |
|------|------|
| `blog_domain` | GitHub Pages 도메인 (예: `https://blog.zionlabs.org`) |
| `keyword_source` | `"trends"`(기본): 실시간 트렌드 / `"tv"`: 방송 편성표 건강·식품 소재 |
| `adsense_client` | 애드센스 승인 후 `ca-pub-XXXXXXXX` 입력 → 광고 스크립트 + ads.txt 자동 생성 |
| `image_mode` | `"ai"`(기본): AI 이미지 생성 포함 / `"free"`: 무료 소스만 사용 |
| `counter_namespace` | 조회수 대시보드(admin.html) 네임스페이스. 비우면 비활성화 |
| `max_posts_per_day` | 하루 최대 발행 수 (기본 3 — 대량 발행은 애드센스 정책 위반 위험) |
| `git_branch` | 배포 브랜치 (GitHub Pages 설정과 일치시킬 것) |

## 검색엔진 등록 (유입의 핵심 — 한 번만 하면 됨)

글을 발행해도 검색엔진에 등록하지 않으면 방문자가 오지 않습니다. 배포 후 반드시 등록하세요.

1. **[Google Search Console](https://search.google.com/search-console)**
   — 도메인 등록(소유 확인) 후 `sitemap.xml` 제출. 애드센스 승인에도 사실상 필수.
2. **[네이버 서치어드바이저](https://searchadvisor.naver.com)**
   — **50대 유입의 최대 통로.** 한국 50대는 네이버 검색 비중이 매우 높습니다.
   사이트 등록 후 `sitemap.xml`과 `rss.xml`을 모두 제출하세요.
3. **[빙 웹마스터 도구](https://www.bing.com/webmasters)** — Search Console 연동으로 1분 만에 등록 가능.

등록 후 색인까지 보통 며칠~몇 주 걸리므로, 그동안 글을 꾸준히 쌓아두는 것이 좋습니다.

## 보안

- **API 키는 절대 코드나 저장소에 넣지 마세요.** `.env` 파일에만 저장하며 `.gitignore`로 제외됩니다.
- 기존 스크립트에 하드코딩되어 있던 Gemini API 키는 노출된 것으로 간주하고
  [Google AI Studio](https://aistudio.google.com/apikey)에서 **삭제 후 재발급**하세요.

## 애드센스 관련 주의

Google은 검색 순위를 노린 대량 자동 생성 콘텐츠를 "확장된 콘텐츠 악용(scaled content abuse)"
스팸 정책으로 제재하며, 적발 시 검색 제외·애드센스 승인 거절/정지가 될 수 있습니다.
안전하게 운영하려면:

- 하루 발행량을 2~3개 이하로 유지 (`max_posts_per_day`)
- 발행된 글을 주기적으로 직접 검토·수정하여 품질 관리
- About/Privacy 페이지 유지 (자동 생성됨 — 내용을 실제 정보로 다듬을 것)
- 애드센스 신청은 글이 30개 이상 쌓이고 실제 방문자가 생긴 뒤에 하는 것을 권장

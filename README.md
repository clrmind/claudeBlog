# AutoBlogger v2 — 50대 타깃 트렌드 자동 블로그

스마트폰(Termux)에서 스케줄러로 자동 실행되어, **50대 독자에게 인기 있는 실시간 키워드**로
칼럼을 생성하고 GitHub Pages에 자동 배포하는 프로그램입니다.

## 동작 방식

```
[스케줄러(cron)] → autoblogger.py 실행
  1. 실시간 트렌드 수집  : 구글 트렌드 KR RSS + signal.bz 실검 TOP10
  2. 키워드 선별 (Gemini): 50대가 가장 클릭할 키워드 1개 선정 (건강/연금/재테크 우선)
  3. 칼럼 생성 (Gemini)  : SEO 제목 + 메타설명 + 2,000자 이상 본문 + FAQ
  4. 사이트 빌드         : index/포스트 HTML, sitemap.xml, rss.xml, robots.txt, ads.txt
  5. GitHub 자동 배포    : commit → pull --rebase → push (재시도 포함)
```

같은 키워드를 반복 발행하지 않도록 최근 100개 발행 이력을 `data/keyword_history.json`에
관리하며, `max_posts_per_day` 설정으로 하루 발행량을 제한합니다.

## 설치 (Termux)

```bash
pkg update && pkg upgrade
pkg install python git cronie termux-services
pip install requests

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

## 설정 (config.json)

| 항목 | 설명 |
|------|------|
| `blog_domain` | GitHub Pages 도메인 (예: `https://blog.zionlabs.org`) |
| `adsense_client` | 애드센스 승인 후 `ca-pub-XXXXXXXX` 입력 → 광고 스크립트 + ads.txt 자동 생성 |
| `counter_namespace` | 조회수 대시보드(admin.html) 네임스페이스. 비우면 비활성화 |
| `max_posts_per_day` | 하루 최대 발행 수 (기본 3 — 대량 발행은 애드센스 정책 위반 위험) |
| `git_branch` | 배포 브랜치 (GitHub Pages 설정과 일치시킬 것) |

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

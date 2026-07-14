# Atlas Not To Do

## Architecture
- Core에서 특정 Plugin을 직접 import하지 않는다.
- Worker가 Gemini, OpenAI, Claude를 직접 호출하지 않는다.
- Provider 이름을 비즈니스 로직에 하드코딩하지 않는다.

## AI
- Search 전에 AI를 호출하지 않는다.
- 규칙으로 해결 가능한 문제를 LLM에 맡기지 않는다.
- 같은 Prompt를 반복 호출하지 않는다.
- 429나 5xx 오류에 무한 재시도하지 않는다.
- AI 실패 때문에 전체 Pipeline을 중단하지 않는다.

## Data
- Knowledge 버전 이력을 삭제하지 않는다.
- 출처 URL과 수집 시각을 제거하지 않는다.
- AI 생성 내용을 원문 사실처럼 저장하지 않는다.

## Development
- 테스트 없는 핵심 기능을 merge하지 않는다.
- 설정값을 여러 위치에 중복 저장하지 않는다.
- 문서 없이 큰 아키텍처 변경을 하지 않는다.

## Product
- 화려한 UI를 핵심 엔진보다 먼저 만들지 않는다.
- 사용자 가치가 불분명한 기능을 우선 개발하지 않는다.
- AI 호출 수를 성장 지표로 삼지 않는다.

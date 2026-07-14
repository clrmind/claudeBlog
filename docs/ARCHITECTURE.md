# Atlas Architecture

## Overview
Atlas는 Core, Runtime, Plugins, Applications, Infrastructure로 분리한다.

```text
Applications
→ Workers
→ Search / Recommendation / Knowledge
→ AI Runtime
→ Providers
→ Storage / Queue / Scheduler / Metrics
```

## Core Rules
1. Core는 Plugin을 알지 않는다.
2. Plugin은 Core만 사용한다.
3. Worker는 Provider를 직접 호출하지 않는다.
4. Router만 Provider를 선택한다.
5. Search와 Recommendation이 AI보다 먼저 실행된다.
6. Rule Engine은 마지막 안전망으로 유지한다.
7. 설정값은 코드에 하드코딩하지 않는다.
8. 모든 기능은 테스트와 함께 추가한다.

## AI Runtime
```text
Worker
→ Router
→ Cache
→ Circuit Breaker
→ Metrics
→ Provider
```

## Providers
- GeminiProvider
- OpenAIProvider
- ClaudeProvider
- OllamaProvider
- RuleProvider

## Applications
- atlas status
- atlas collect
- atlas run
- atlas index
- atlas search
- atlas recommend
- atlas ask
- atlas test
- atlas health

향후:
- atlas doctor
- atlas verify
- atlas dashboard
- atlas planner

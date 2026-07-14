# Atlas v1.0.0-rc2 Release Notes

Atlas has reached its second Release Candidate.

This release packages the Government Knowledge Platform, provider-independent AI Runtime, observability, system diagnostics, and end-to-end verification into a unified CLI product.

## Highlights

- Government support program collection and normalization
- Versioned Knowledge Store
- Search and recommendation engine
- Provider-based AI Runtime
- Gemini provider, caching, and circuit breaker
- Runtime metrics and cache-hit tracking
- System health diagnostics
- End-to-end product verification
- 25 automated tests

## Operations

```bash
python -m atlas test
python -m atlas doctor
python -m atlas verify
python -m atlas metrics

# Changelog

All notable changes to Atlas are documented in this file.

The format follows Keep a Changelog, and this project follows Semantic Versioning.

## [1.0.0-rc2] - 2026-07-15

### Added

#### Core
- Unified Atlas CLI
- Regression test framework

#### Government
- Government support program collection pipeline
- Normalized Knowledge Store with version history
- Attachment collection and preservation
- SQLite search index
- Rule-based tagging and recommendation

#### AI Runtime
- Provider abstraction
- Gemini provider
- Provider registry
- AI router
- Response cache
- Circuit breaker

#### Observability
- SQLite metrics recorder
- Provider latency and success tracking
- Cache-hit tracking
- `python -m atlas metrics`

#### Operations
- `python -m atlas doctor`
- `python -m atlas verify`
- Health-check and verification exit codes

#### Testing
- 25 automated unit and integration tests

### Changed
- Consolidated operational commands into the Atlas CLI
- Decoupled AI calls from provider-specific business logic
- Connected runtime operations to metrics collection

### Fixed
- Runtime AI calls not being recorded
- Cached responses missing from metrics
- Gemini API key detection from `.env`

## [1.0.0-rc1] - 2026-07-15

### Added
- Initial Atlas Release Candidate tag

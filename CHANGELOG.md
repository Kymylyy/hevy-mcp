# Changelog

All notable changes to this project will be documented in this file.

## 1.0.0 - 2026-02-23

### Added

- OSS repository baseline documents (`LICENSE`, `CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`).
- GitHub Actions workflows for CI and release-readiness checks.
- Comprehensive tests for all MCP tools and response contract behavior.

### Changed

- Refactored tool implementations from a monolithic module into focused submodules.
- Improved service typing boundaries using a client protocol.
- Introduced structured tool-event logging adapter while preserving JSON log format.
- Updated packaging metadata for public OSS release readiness.

### Removed

- Internal-only files from tracked repository artifacts.

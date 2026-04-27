# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-17

### Added

- Initial project structure with Vue 3 + Vite + Tauri 2 + Tailwind CSS 4
- iOS App Store style game list interface
- Category filtering and search functionality
- 2048 game with full implementation
  - Touch swipe and keyboard arrow controls
  - Game state persistence (localStorage fallback / Tauri file storage)
  - Win/lose detection and restart functionality
- Tauri backend for game state storage (Rust)
- GitHub Actions CI/CD for multi-platform builds (Windows, macOS, Linux, Android)
- ESLint and Prettier configuration
- Unit test setup with Vitest
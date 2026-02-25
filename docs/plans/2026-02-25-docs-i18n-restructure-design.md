# Docs i18n Restructure Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make English the primary language for all root-level markdown files, with translations consolidated into a language-first `docs/i18n/<lang>/` directory structure.

**Architecture:** Root files (README.md, GEMINI.md, devcontainer docs) become English-primary. All translations move to `docs/i18n/<lang>/`. CLAUDE.md becomes bilingual (Chinese + English inline), no i18n versions needed.

**Motivation:** GitHub renders root-level markdown files first. English-primary content maximizes global discoverability. Language-first i18n structure (one folder per language) is easier to maintain and navigate than document-first (one folder per doc type).

---

## Root-Level File Changes

| File | Before | After |
|------|--------|-------|
| `README.md` | Chinese primary | **English primary** (use existing `docs/i18n/readme/README.en.md` content) |
| `GEMINI.md` | Chinese primary | **English primary** (use existing `docs/i18n/gemini-md/GEMINI.en.md` content) |
| `CLAUDE.md` | Chinese primary | **Bilingual** (Chinese + English inline, section-by-section) |
| `CODE_OF_CONDUCT.md` | English ✓ | No change |
| `SECURITY.md` | English ✓ | No change |
| `.github/CONTRIBUTING.md` | English ✓ | No change |
| `.devcontainer/README.md` | Chinese primary | **English primary** |
| `.devcontainer/QUICK_START.md` | Chinese primary | **English primary** |

## New i18n Directory Structure

Language-first layout under `docs/i18n/`:

```
docs/i18n/
├── zh/
│   ├── README.md               (from docs/i18n/readme/README.md → current root README.md)
│   ├── GEMINI.md               (from current root GEMINI.md)
│   ├── CODE_OF_CONDUCT.md      (from docs/i18n/code-of-conduct/CODE_OF_CONDUCT.zh.md)
│   ├── SECURITY.md             (from docs/i18n/security/SECURITY.zh.md)
│   ├── CONTRIBUTING.md         (from docs/i18n/contributing/CONTRIBUTING.zh.md)
│   └── devcontainer/
│       ├── README.md           (from .devcontainer/README.md current Chinese content)
│       └── QUICK_START.md      (from .devcontainer/QUICK_START.md current Chinese content)
├── ja/
│   ├── README.md               (from docs/i18n/readme/README.ja.md)
│   ├── GEMINI.md               (from docs/i18n/gemini-md/GEMINI.ja.md)
│   └── devcontainer/
│       ├── README.md           (from .devcontainer/docs/i18n/readme/README.ja.md)
│       └── QUICK_START.md      (from .devcontainer/docs/i18n/quick-start/QUICK_START.ja.md)
├── ko/
│   ├── README.md               (from docs/i18n/readme/README.ko.md)
│   ├── GEMINI.md               (from docs/i18n/gemini-md/GEMINI.ko.md)
│   └── devcontainer/
│       ├── README.md           (from .devcontainer/docs/i18n/readme/README.ko.md)
│       └── QUICK_START.md      (from .devcontainer/docs/i18n/quick-start/QUICK_START.ko.md)
├── fr/
│   ├── README.md               (from docs/i18n/readme/README.fr.md)
│   ├── GEMINI.md               (from docs/i18n/gemini-md/GEMINI.fr.md)
│   └── devcontainer/
│       ├── README.md           (from .devcontainer/docs/i18n/readme/README.fr.md)
│       └── QUICK_START.md      (from .devcontainer/docs/i18n/quick-start/QUICK_START.fr.md)
└── de/
    ├── README.md               (from docs/i18n/readme/README.de.md)
    ├── GEMINI.md               (from docs/i18n/gemini-md/GEMINI.de.md)
    └── devcontainer/
        ├── README.md           (from .devcontainer/docs/i18n/readme/README.de.md)
        └── QUICK_START.md      (from .devcontainer/docs/i18n/quick-start/QUICK_START.de.md)
```

## Old Directories to Delete

After migrating content:

- `docs/i18n/readme/`          → content moved to `docs/i18n/<lang>/README.md`
- `docs/i18n/claude-md/`       → deleted entirely (CLAUDE.md goes bilingual)
- `docs/i18n/gemini-md/`       → content moved to `docs/i18n/<lang>/GEMINI.md`
- `docs/i18n/code-of-conduct/` → content moved to `docs/i18n/zh/CODE_OF_CONDUCT.md`
- `docs/i18n/contributing/`    → content moved to `docs/i18n/zh/CONTRIBUTING.md`
- `docs/i18n/security/`        → content moved to `docs/i18n/zh/SECURITY.md`
- `.devcontainer/docs/`        → content moved to `docs/i18n/<lang>/devcontainer/`

## Language Badge Link Pattern

Top of each root-level file:

```markdown
[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)
```

Each i18n file links back to root:

```markdown
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | ...
```

## CLAUDE.md Bilingual Format

Section headers are English only. Body text appears in both languages inline:

```markdown
# CLAUDE.md — AI Agent Instructions

## Branch Strategy / 分支策略

Work on `dev` branch. Never commit directly to `main`.
在 `dev` 分支开发，禁止直接提交到 `main`。

### Branch Naming / 分支命名
...
```

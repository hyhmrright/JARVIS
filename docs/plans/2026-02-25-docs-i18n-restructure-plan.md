# Docs i18n Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize all markdown documentation so English is the primary language in root-level files, with all translations consolidated into a unified `docs/i18n/<lang>/` language-first directory structure.

**Architecture:** File migration + content rewrite. No code changes. Each task migrates one logical group of files, updates all internal cross-reference links, and commits. Old directories are deleted in the final task.

**Tech Stack:** Git, markdown, bash (for mkdir/git mv)

**Design doc:** `docs/plans/2026-02-25-docs-i18n-restructure-design.md`

---

## Link Reference Guide

After restructuring, every file's language nav bar uses these relative paths:

**Root-level files** (`README.md`, `GEMINI.md`):
```
[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)
```

**`docs/i18n/zh/README.md`** (3 levels deep):
```
[English](../../../README.md) | [中文](README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)
```

**`docs/i18n/ja/README.md`** (and ko, fr, de — same depth):
```
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)
```

**`.devcontainer/README.md`** (root-level devcontainer):
```
[中文](../docs/i18n/zh/devcontainer/README.md) | [日本語](../docs/i18n/ja/devcontainer/README.md) | [한국어](../docs/i18n/ko/devcontainer/README.md) | [Français](../docs/i18n/fr/devcontainer/README.md) | [Deutsch](../docs/i18n/de/devcontainer/README.md)
```

**`docs/i18n/zh/devcontainer/README.md`** (4 levels deep):
```
[English](../../../../.devcontainer/README.md) | [中文](README.md) | [日本語](../../ja/devcontainer/README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)
```

**`docs/i18n/ja/devcontainer/README.md`** (and ko, fr, de):
```
[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)
```

---

### Task 1: Create directory structure

**Files:**
- Create: `docs/i18n/zh/`, `docs/i18n/zh/devcontainer/`
- Create: `docs/i18n/ja/devcontainer/`, `docs/i18n/ko/devcontainer/`
- Create: `docs/i18n/fr/devcontainer/`, `docs/i18n/de/devcontainer/`

**Step 1: Create all new directories**

```bash
mkdir -p docs/i18n/zh/devcontainer
mkdir -p docs/i18n/ja/devcontainer
mkdir -p docs/i18n/ko/devcontainer
mkdir -p docs/i18n/fr/devcontainer
mkdir -p docs/i18n/de/devcontainer
```

**Step 2: Verify directories exist**

```bash
find docs/i18n -type d | sort
```

Expected output:
```
docs/i18n/de
docs/i18n/de/devcontainer
docs/i18n/fr
docs/i18n/fr/devcontainer
docs/i18n/ja
docs/i18n/ja/devcontainer
docs/i18n/ko
docs/i18n/ko/devcontainer
docs/i18n/zh
docs/i18n/zh/devcontainer
```

(Old subdirs like `docs/i18n/readme/` also appear — that's fine, they'll be removed later.)

No commit needed — empty directories aren't tracked by git. Proceed to Task 2.

---

### Task 2: Migrate README translations (zh, ja, ko, fr, de)

**Files:**
- Create: `docs/i18n/zh/README.md` (content = current `README.md` but with updated links)
- Create: `docs/i18n/ja/README.md` (content = current `docs/i18n/readme/README.ja.md` with updated links)
- Create: `docs/i18n/ko/README.md` (content = current `docs/i18n/readme/README.ko.md` with updated links)
- Create: `docs/i18n/fr/README.md` (content = current `docs/i18n/readme/README.fr.md` with updated links)
- Create: `docs/i18n/de/README.md` (content = current `docs/i18n/readme/README.de.md` with updated links)

**Step 1: Copy zh README (= current root README.md content)**

Read `/Users/hyh/code/JARVIS/README.md`. Replace only the language nav bar (line 1) with:
```
[English](../../../README.md) | [中文](README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)
```
Write to `docs/i18n/zh/README.md`.

**Step 2: Copy ja README**

Read `docs/i18n/readme/README.ja.md`. Replace line 1 with:
```
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)
```
Write to `docs/i18n/ja/README.md`.

**Step 3: Copy ko README**

Read `docs/i18n/readme/README.ko.md`. Replace line 1 with:
```
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)
```
Write to `docs/i18n/ko/README.md`.

**Step 4: Copy fr README**

Read `docs/i18n/readme/README.fr.md`. Replace line 1 with:
```
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](README.md) | [Deutsch](../de/README.md)
```
Write to `docs/i18n/fr/README.md`.

**Step 5: Copy de README**

Read `docs/i18n/readme/README.de.md`. Replace line 1 with:
```
[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](README.md)
```
Write to `docs/i18n/de/README.md`.

**Step 6: Verify files created**

```bash
ls docs/i18n/zh/README.md docs/i18n/ja/README.md docs/i18n/ko/README.md docs/i18n/fr/README.md docs/i18n/de/README.md
```

Expected: all 5 files listed, no errors.

**Step 7: Commit**

```bash
git add docs/i18n/zh/README.md docs/i18n/ja/README.md docs/i18n/ko/README.md docs/i18n/fr/README.md docs/i18n/de/README.md
git commit -m "docs(i18n): migrate README translations to language-first structure"
```

---

### Task 3: Migrate GEMINI translations (zh, ja, ko, fr, de)

**Files:**
- Create: `docs/i18n/zh/GEMINI.md` (content = current `GEMINI.md` with updated links)
- Create: `docs/i18n/ja/GEMINI.md` (content = current `docs/i18n/gemini-md/GEMINI.ja.md` with updated links)
- Create: `docs/i18n/ko/GEMINI.md`, `docs/i18n/fr/GEMINI.md`, `docs/i18n/de/GEMINI.md`

**Step 1: Copy zh GEMINI (= current root GEMINI.md content)**

Read `GEMINI.md`. Replace line 1 with:
```
[English](../../../GEMINI.md) | [中文](GEMINI.md) | [日本語](../ja/GEMINI.md) | [한국어](../ko/GEMINI.md) | [Français](../fr/GEMINI.md) | [Deutsch](../de/GEMINI.md)
```
Write to `docs/i18n/zh/GEMINI.md`.

**Step 2: Copy ja GEMINI**

Read `docs/i18n/gemini-md/GEMINI.ja.md`. Replace line 1 with:
```
[English](../../../GEMINI.md) | [中文](../zh/GEMINI.md) | [日本語](GEMINI.md) | [한국어](../ko/GEMINI.md) | [Français](../fr/GEMINI.md) | [Deutsch](../de/GEMINI.md)
```
Write to `docs/i18n/ja/GEMINI.md`.

**Step 3: Copy ko GEMINI**

Read `docs/i18n/gemini-md/GEMINI.ko.md`. Replace line 1 with:
```
[English](../../../GEMINI.md) | [中文](../zh/GEMINI.md) | [日本語](../ja/GEMINI.md) | [한국어](GEMINI.md) | [Français](../fr/GEMINI.md) | [Deutsch](../de/GEMINI.md)
```
Write to `docs/i18n/ko/GEMINI.md`.

**Step 4: Copy fr GEMINI**

Read `docs/i18n/gemini-md/GEMINI.fr.md`. Replace line 1 with:
```
[English](../../../GEMINI.md) | [中文](../zh/GEMINI.md) | [日本語](../ja/GEMINI.md) | [한국어](../ko/GEMINI.md) | [Français](GEMINI.md) | [Deutsch](../de/GEMINI.md)
```
Write to `docs/i18n/fr/GEMINI.md`.

**Step 5: Copy de GEMINI**

Read `docs/i18n/gemini-md/GEMINI.de.md`. Replace line 1 with:
```
[English](../../../GEMINI.md) | [中文](../zh/GEMINI.md) | [日本語](../ja/GEMINI.md) | [한국어](../ko/GEMINI.md) | [Français](../fr/GEMINI.md) | [Deutsch](GEMINI.md)
```
Write to `docs/i18n/de/GEMINI.md`.

**Step 6: Commit**

```bash
git add docs/i18n/zh/GEMINI.md docs/i18n/ja/GEMINI.md docs/i18n/ko/GEMINI.md docs/i18n/fr/GEMINI.md docs/i18n/de/GEMINI.md
git commit -m "docs(i18n): migrate GEMINI translations to language-first structure"
```

---

### Task 4: Migrate zh-only translations (CODE_OF_CONDUCT, SECURITY, CONTRIBUTING)

**Files:**
- Create: `docs/i18n/zh/CODE_OF_CONDUCT.md` (from `docs/i18n/code-of-conduct/CODE_OF_CONDUCT.zh.md`)
- Create: `docs/i18n/zh/SECURITY.md` (from `docs/i18n/security/SECURITY.zh.md`)
- Create: `docs/i18n/zh/CONTRIBUTING.md` (from `docs/i18n/contributing/CONTRIBUTING.zh.md`)

**Step 1: Read and check existing files**

```bash
head -3 docs/i18n/code-of-conduct/CODE_OF_CONDUCT.zh.md
head -3 docs/i18n/security/SECURITY.zh.md
head -3 docs/i18n/contributing/CONTRIBUTING.zh.md
```

**Step 2: Copy CODE_OF_CONDUCT**

Read `docs/i18n/code-of-conduct/CODE_OF_CONDUCT.zh.md`. Replace line 1 with:
```
[English](../../../CODE_OF_CONDUCT.md) | [中文](CODE_OF_CONDUCT.md)
```
Write to `docs/i18n/zh/CODE_OF_CONDUCT.md`.

**Step 3: Copy SECURITY**

Read `docs/i18n/security/SECURITY.zh.md`. Replace line 1 with:
```
[English](../../../SECURITY.md) | [中文](SECURITY.md)
```
Write to `docs/i18n/zh/SECURITY.md`.

**Step 4: Copy CONTRIBUTING**

Read `docs/i18n/contributing/CONTRIBUTING.zh.md`. Replace line 1 with:
```
[English](../../../.github/CONTRIBUTING.md) | [中文](CONTRIBUTING.md)
```
Write to `docs/i18n/zh/CONTRIBUTING.md`.

**Step 5: Update back-links in root English files**

Modify `CODE_OF_CONDUCT.md` line 1 from:
```
[English](CODE_OF_CONDUCT.md) | [中文](docs/i18n/code-of-conduct/CODE_OF_CONDUCT.zh.md)
```
To:
```
[English](CODE_OF_CONDUCT.md) | [中文](docs/i18n/zh/CODE_OF_CONDUCT.md)
```

Modify `SECURITY.md` line 1 from:
```
[English](SECURITY.md) | [中文](docs/i18n/security/SECURITY.zh.md)
```
To:
```
[English](SECURITY.md) | [中文](docs/i18n/zh/SECURITY.md)
```

Modify `.github/CONTRIBUTING.md` line 1 from:
```
[English](CONTRIBUTING.md) | [中文](../docs/i18n/contributing/CONTRIBUTING.zh.md)
```
To:
```
[English](CONTRIBUTING.md) | [中文](../docs/i18n/zh/CONTRIBUTING.md)
```

**Step 6: Commit**

```bash
git add docs/i18n/zh/CODE_OF_CONDUCT.md docs/i18n/zh/SECURITY.md docs/i18n/zh/CONTRIBUTING.md
git add CODE_OF_CONDUCT.md SECURITY.md .github/CONTRIBUTING.md
git commit -m "docs(i18n): migrate zh-only translations, update back-links"
```

---

### Task 5: Migrate devcontainer translations (all 5 languages)

**Files:**
- Create: `docs/i18n/zh/devcontainer/README.md` (from `.devcontainer/README.md` Chinese content)
- Create: `docs/i18n/zh/devcontainer/QUICK_START.md` (from `.devcontainer/QUICK_START.md` Chinese content)
- Create: `docs/i18n/ja/devcontainer/README.md` (from `.devcontainer/docs/i18n/readme/README.ja.md`)
- Create: `docs/i18n/ja/devcontainer/QUICK_START.md` (from `.devcontainer/docs/i18n/quick-start/QUICK_START.ja.md`)
- Same for ko, fr, de

**Step 1: Copy zh devcontainer README (= current .devcontainer/README.md content)**

Read `.devcontainer/README.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/README.md) | [中文](README.md) | [日本語](../../ja/devcontainer/README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)
```
Write to `docs/i18n/zh/devcontainer/README.md`.

**Step 2: Copy zh devcontainer QUICK_START (= current .devcontainer/QUICK_START.md content)**

Read `.devcontainer/QUICK_START.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/QUICK_START.md) | [中文](QUICK_START.md) | [日本語](../../ja/devcontainer/QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](../../de/devcontainer/QUICK_START.md)
```
Write to `docs/i18n/zh/devcontainer/QUICK_START.md`.

**Step 3: Copy ja devcontainer files**

Read `.devcontainer/docs/i18n/readme/README.ja.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)
```
Write to `docs/i18n/ja/devcontainer/README.md`.

Read `.devcontainer/docs/i18n/quick-start/QUICK_START.ja.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](../../de/devcontainer/QUICK_START.md)
```
Write to `docs/i18n/ja/devcontainer/QUICK_START.md`.

**Step 4: Copy ko devcontainer files**

Read `.devcontainer/docs/i18n/readme/README.ko.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](../../ja/devcontainer/README.md) | [한국어](README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](../../de/devcontainer/README.md)
```
Write to `docs/i18n/ko/devcontainer/README.md`.

Read `.devcontainer/docs/i18n/quick-start/QUICK_START.ko.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](../../ja/devcontainer/QUICK_START.md) | [한국어](QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](../../de/devcontainer/QUICK_START.md)
```
Write to `docs/i18n/ko/devcontainer/QUICK_START.md`.

**Step 5: Copy fr devcontainer files**

Read `.devcontainer/docs/i18n/readme/README.fr.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](../../ja/devcontainer/README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](README.md) | [Deutsch](../../de/devcontainer/README.md)
```
Write to `docs/i18n/fr/devcontainer/README.md`.

Read `.devcontainer/docs/i18n/quick-start/QUICK_START.fr.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](../../ja/devcontainer/QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](QUICK_START.md) | [Deutsch](../../de/devcontainer/QUICK_START.md)
```
Write to `docs/i18n/fr/devcontainer/QUICK_START.md`.

**Step 6: Copy de devcontainer files**

Read `.devcontainer/docs/i18n/readme/README.de.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/README.md) | [中文](../../zh/devcontainer/README.md) | [日本語](../../ja/devcontainer/README.md) | [한국어](../../ko/devcontainer/README.md) | [Français](../../fr/devcontainer/README.md) | [Deutsch](README.md)
```
Write to `docs/i18n/de/devcontainer/README.md`.

Read `.devcontainer/docs/i18n/quick-start/QUICK_START.de.md`. Replace line 1 with:
```
[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](../../ja/devcontainer/QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](QUICK_START.md)
```
Write to `docs/i18n/de/devcontainer/QUICK_START.md`.

**Step 7: Commit**

```bash
git add docs/i18n/zh/devcontainer/ docs/i18n/ja/devcontainer/ docs/i18n/ko/devcontainer/ docs/i18n/fr/devcontainer/ docs/i18n/de/devcontainer/
git commit -m "docs(i18n): migrate devcontainer translations to language-first structure"
```

---

### Task 6: Rewrite root README.md → English primary

**Files:**
- Modify: `README.md`

**Step 1: Replace README.md content**

Read `docs/i18n/readme/README.en.md`. The content is the English version. Copy it entirely, but replace line 1 with:
```
[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)
```
Write the result to `README.md` (overwrite).

**Step 2: Verify README is now English**

```bash
head -5 README.md
```

Expected:
```
[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)

# JARVIS

An AI assistant platform with RAG knowledge base...
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: make README.md English primary"
```

---

### Task 7: Rewrite root GEMINI.md → English primary

**Files:**
- Modify: `GEMINI.md`

**Step 1: Replace GEMINI.md content**

Read `docs/i18n/gemini-md/GEMINI.en.md`. Copy entirely, replace line 1 with:
```
[中文](docs/i18n/zh/GEMINI.md) | [日本語](docs/i18n/ja/GEMINI.md) | [한국어](docs/i18n/ko/GEMINI.md) | [Français](docs/i18n/fr/GEMINI.md) | [Deutsch](docs/i18n/de/GEMINI.md)
```
Write to `GEMINI.md`.

**Step 2: Verify**

```bash
head -5 GEMINI.md
```

Expected first line: `[中文](docs/i18n/zh/GEMINI.md) | ...`
Expected content language: English.

**Step 3: Commit**

```bash
git add GEMINI.md
git commit -m "docs: make GEMINI.md English primary"
```

---

### Task 8: Rewrite .devcontainer English primary

**Files:**
- Modify: `.devcontainer/README.md`
- Modify: `.devcontainer/QUICK_START.md`

**Step 1: Replace .devcontainer/README.md**

Read `.devcontainer/docs/i18n/readme/README.en.md`. Copy entirely, replace line 1 with:
```
[中文](../docs/i18n/zh/devcontainer/README.md) | [日本語](../docs/i18n/ja/devcontainer/README.md) | [한국어](../docs/i18n/ko/devcontainer/README.md) | [Français](../docs/i18n/fr/devcontainer/README.md) | [Deutsch](../docs/i18n/de/devcontainer/README.md)
```
Write to `.devcontainer/README.md`.

**Step 2: Replace .devcontainer/QUICK_START.md**

Read `.devcontainer/docs/i18n/quick-start/QUICK_START.en.md`. Copy entirely, replace line 1 with:
```
[中文](../docs/i18n/zh/devcontainer/QUICK_START.md) | [日本語](../docs/i18n/ja/devcontainer/QUICK_START.md) | [한국어](../docs/i18n/ko/devcontainer/QUICK_START.md) | [Français](../docs/i18n/fr/devcontainer/QUICK_START.md) | [Deutsch](../docs/i18n/de/devcontainer/QUICK_START.md)
```
Write to `.devcontainer/QUICK_START.md`.

**Step 3: Commit**

```bash
git add .devcontainer/README.md .devcontainer/QUICK_START.md
git commit -m "docs: make devcontainer docs English primary"
```

---

### Task 9: Rewrite CLAUDE.md → bilingual

**Files:**
- Modify: `CLAUDE.md`
- Source: `CLAUDE.md` (Chinese, 343 lines) + `docs/i18n/claude-md/CLAUDE.en.md` (English, 262 lines)

**Step 1: Understand the approach**

CLAUDE.md becomes a single bilingual file. Format:
- Remove the language nav bar (line 1) entirely
- Section headings: English / 中文 side by side in the heading
- Body: English paragraph first, Chinese paragraph below, separated by blank line
- Code blocks: not duplicated (commands are universal)
- Tables: not duplicated (too verbose — English only is fine for tables)

Example structure:
```markdown
# CLAUDE.md — AI Agent Instructions / AI 编程助手指南

This file provides guidance to Claude Code when working in this repository.
本文件为 Claude Code 在此代码库中工作时提供指导。

## Branch Strategy / 分支策略

- **main**: Release only. Never commit or develop directly here.
- **dev**: Primary development branch. All daily work happens here.

- **main**：仅用于发版，不得直接提交或开发。
- **dev**：主开发分支，所有日常开发在此进行。
```

**Step 2: Read both source files**

Read `CLAUDE.md` and `docs/i18n/claude-md/CLAUDE.en.md` to understand the full content of each.

**Step 3: Write the bilingual CLAUDE.md**

Merge the two files section by section. The new file should:
- Start with `# CLAUDE.md — AI Agent Instructions / AI 编程助手指南` (no language nav)
- For each section: English heading + body first, Chinese body below
- Keep all command blocks (bash, etc.) only once — they're language-agnostic
- Keep tables once (English) to avoid duplication
- Preserve all technical content from both versions (neither version should lose unique content)

Write the merged result to `CLAUDE.md`.

**Step 4: Verify the file looks correct**

```bash
head -20 CLAUDE.md
wc -l CLAUDE.md
```

Expected: No language nav on line 1. File starts with `# CLAUDE.md`. Roughly 350-450 lines (merged but DRY).

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md as bilingual (Chinese + English inline)"
```

---

### Task 10: Delete old directory structure

**Files to delete:**
- `docs/i18n/readme/` (5 files)
- `docs/i18n/claude-md/` (5 files)
- `docs/i18n/gemini-md/` (5 files)
- `docs/i18n/code-of-conduct/` (1 file)
- `docs/i18n/contributing/` (1 file)
- `docs/i18n/security/` (1 file)
- `.devcontainer/docs/` (10 files across 2 subdirs)

**Step 1: Remove old directories**

```bash
git rm -r docs/i18n/readme/
git rm -r docs/i18n/claude-md/
git rm -r docs/i18n/gemini-md/
git rm -r docs/i18n/code-of-conduct/
git rm -r docs/i18n/contributing/
git rm -r docs/i18n/security/
git rm -r .devcontainer/docs/
```

**Step 2: Verify old dirs are gone**

```bash
find docs/i18n -type d | sort
```

Expected — only the new language dirs remain:
```
docs/i18n/de
docs/i18n/de/devcontainer
docs/i18n/fr
docs/i18n/fr/devcontainer
docs/i18n/ja
docs/i18n/ja/devcontainer
docs/i18n/ko
docs/i18n/ko/devcontainer
docs/i18n/zh
docs/i18n/zh/devcontainer
```

Also check `.devcontainer/` has no `docs/` subfolder:
```bash
ls .devcontainer/
```

**Step 3: Commit**

```bash
git commit -m "docs(i18n): remove old scattered i18n directories"
```

---

### Task 11: Verify and fix all broken links

**Step 1: Check for any remaining old path references**

```bash
# Search for any markdown links still pointing to old paths
grep -r "docs/i18n/readme/" . --include="*.md" | grep -v ".git"
grep -r "docs/i18n/claude-md/" . --include="*.md" | grep -v ".git"
grep -r "docs/i18n/gemini-md/" . --include="*.md" | grep -v ".git"
grep -r "docs/i18n/code-of-conduct/" . --include="*.md" | grep -v ".git"
grep -r "docs/i18n/contributing/" . --include="*.md" | grep -v ".git"
grep -r "docs/i18n/security/" . --include="*.md" | grep -v ".git"
grep -r ".devcontainer/docs/" . --include="*.md" | grep -v ".git"
```

Expected: no output (no remaining references to old paths).

**Step 2: Fix any found references**

If any references are found, use Edit tool to update them to the new paths.

**Step 3: Check nav bars in i18n files**

Spot-check a few files:
```bash
head -1 docs/i18n/zh/README.md
head -1 docs/i18n/ja/README.md
head -1 docs/i18n/zh/devcontainer/README.md
head -1 docs/i18n/de/GEMINI.md
```

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "docs(i18n): fix any remaining stale cross-reference links"
```

(Skip this commit if there's nothing to fix.)

---

### Task 12: Final verification

**Step 1: Count all markdown files**

```bash
find . -name "*.md" | grep -v ".git" | grep -v ".worktrees" | grep -v "node_modules" | grep -v ".venv" | grep -v "pytest_cache" | sort
```

**Step 2: Verify root files are English**

```bash
head -3 README.md
head -3 GEMINI.md
head -3 .devcontainer/README.md
head -3 .devcontainer/QUICK_START.md
```

Each should start with a language nav (no `[English]` bullet — it IS the English) followed by English content.

**Step 3: Verify zh translations exist and are Chinese**

```bash
head -3 docs/i18n/zh/README.md
head -3 docs/i18n/zh/GEMINI.md
head -3 docs/i18n/zh/devcontainer/README.md
```

**Step 4: Verify CLAUDE.md is bilingual**

```bash
head -5 CLAUDE.md
grep -c "##" CLAUDE.md
```

Should have no language nav on line 1, and contains section headings.

**Step 5: Final commit if needed, then push**

```bash
git status
# If clean:
git push origin dev
```

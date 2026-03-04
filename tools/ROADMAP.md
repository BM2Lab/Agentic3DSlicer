# Tools Infrastructure Roadmap

This roadmap tracks the evolution of the tool library's discovery and storage infrastructure
as the project scales toward community publication.

---

## Phase 1 — Foundation (Current)

**Scale:** 0–50 tools
**Status:** Active

### What's in place

- **`tools/index.json`** — machine-readable index; every tool has `id`, `file`, `category`, `description`, `tags`, `usage`, `slicer_version`, `verified`
- **`tools/README.md`** — human-readable companion with per-category tables
- **Flat file structure** — scripts organized by category folder (`scene/`, `volumes/`, `visualization/`, `io/`, `segmentation/`, `automation/`, `snippets/`)
- **Tags in script headers** — every script carries a `Tags:` field for fast grep-based search
- **Anonymity rule** — no user-identifying paths, names, or hostnames in any file

### How agents find tools

1. Read `tools/index.json` (compact, ~1–2 KB for 50 tools)
2. Filter by `category` or search `tags` / `description`
3. Fetch only the matched script file

### Checklist before moving to Phase 2

- [ ] Tool count exceeds ~50
- [ ] `index.json` searches feel slow or miss things due to keyword limitations
- [ ] Contributors outside the core team are submitting tools (needs validation automation)

---

## Phase 2 — Discovery (~50–200 tools)

**Scale:** 50–200 tools
**Status:** Planned — implement when Phase 1 checklist is met

### Goals

- Agents find tools faster and more accurately, even with partial or semantic queries
- New tool submissions are validated automatically
- The library is ready for community announcement (Slicer Discourse, GitHub)

### What to build

#### 2a. SQLite Index (`tools/tools.db`)

Generate a SQLite database from `index.json` using a build script (`tools/build-db.py`).
Enables fast structured queries without reading JSON in Python:

```sql
SELECT file, description FROM tools WHERE tags LIKE '%screenshot%';
SELECT file FROM tools WHERE category = 'visualization' ORDER BY verified DESC;
```

- Keep `index.json` as the source of truth — `tools.db` is always regenerated from it
- Add `tools/search.py` — a CLI tool agents can call instead of parsing JSON manually:
  ```
  python tools/search.py --query "capture screenshot"
  python tools/search.py --category visualization
  ```

#### 2b. Tags → Full-Text Search

Extend the SQLite schema to include the full script body for full-text search (FTS5).
Agents can find tools by code patterns, not just metadata.

#### 2c. GitHub Actions CI

On every pull request that touches `tools/`:
- Validate that new/modified scripts have all required header fields (`Tool`, `Category`, `Tags`, `Description`, `Usage`, `Version`, `Verified`)
- Validate that `index.json` has been updated to include the new tool
- Lint Python scripts with `flake8` or `ruff`
- Check for identity leakage (grep for common patterns like `/home/`, email addresses)

#### 2d. CONTRIBUTING.md

Public contribution guide covering:
- How to add a tool (same process as `SKILL.md` but written for external contributors)
- Header format and tag guidelines
- How to run the validation CI locally before submitting a PR
- Code of conduct
  
---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-04 | Use `index.json` as primary index instead of README tables | README is for humans; JSON is for agents and scripts. Scales cleanly to SQLite in Phase 2 without changing the schema. |
| 2026-03-04 | Add `Tags:` field to all script headers | Enables cheap grep-based discovery without loading full scripts. Tags in headers stay in sync with `index.json` entries. |
| 2026-03-04 | Defer vector/semantic search to post-Phase 2 | Overkill below ~200 tools. SQLite FTS5 covers most retrieval needs at this scale. |

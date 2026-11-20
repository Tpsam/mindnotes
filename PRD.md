# PRD: MINDNOTES v1.3

**Owner:** Samuel  
**Status:** Ready for Build (v1.3 - Post-Grill Revision)  
**Last updated:** 2026-11-20  

---

## 1. Problem Statement

Ideas and conversations get lost between the moment they happen (in your head, in a recording) and the moment they're usable (a note, a script, a post). Today this requires manual transcription and manual restructuring, both of which create enough friction that raw audio piles up instead of becoming output.

This tool closes that gap with one lightweight, UI-agnostic, reusable pipeline — **audio in, structured text out** — that serves two distinct use cases:

1. **Quick Notes mode** — voice memo → first-draft structured note with verbatim transcript in a collapsible toggle
2. **Content mode** — podcast/interview recording → speaker-attributed transcript, show notes, pull quotes with timestamps, and social post ideas

Both modes share the same lightweight ONNX transcription core (`sherpa-onnx`) running 100% locally on CPU and differ only in diarization flags and the downstream structuring step. Building one core engine (`pipeline.py`) decoupled from any interface avoids duplicating STT/chaining infrastructure and lets multiple triggers (watched folders with Windows background autostart, CLI / Windows "Send To" context menu, and a lightweight local Web UI) call the exact same backend.

---

## 2. Goals

* Turn a raw audio file into usable structured text with near-zero trigger friction.
* Run transcription and speaker diarization **100% locally on a lightweight runtime** (`sherpa-onnx` via ONNX Runtime — no PyTorch/CUDA gigabytes, no audio leaving your machine).
* Push structured output directly into Notion, ready to act on, with verbatim transcript in collapsible toggle (Notes) or local file path reference (Content).
* Be reusable across both personal note-taking and LIAS/Ose Studios content production.
* Eliminate workflow friction to counter the "planning without following through" pattern — dropping a file into a folder (backed by a silent Windows background service), right-clicking via "Send To", or clicking a local UI button must work reliably every day.
* Ensure zero data loss via local-first JSON/Markdown caching in `~/Mindnotes/output` and a Phase 1 `--retry-cached` synchronization command.

---

## 3. Non-Goals (v1)

* Heavy ML runtimes (PyTorch, CUDA toolkits, CTranslate2, WhisperX) — replaced by lightweight CPU/ONNX models via `sherpa-onnx`.
* Real-time/live transcription (batch processing of finished recordings only).
* Native Windows desktop GUI (PyQt/Tkinter/CustomTkinter) — avoided due to threading complexity and UI boilerplate.
* Mobile app or hosted public cloud app — local triggers only.
* Multi-language transcription beyond English (Yoruba/Pidgin STT/ASR is a separate research track and out of scope here).

---

## 4. Users

Single user (Samuel). No auth, no multi-tenancy, no complex permissions model. Optimize entirely for personal workflow speed, low resource footprint on Windows, and zero maintenance overhead.

---

## 5. Core Pipeline Architecture

The core engine (`pipeline.py`) is completely decoupled from entrypoints and user interface:

```
                    ┌──► [Watched Folders: ~/Mindnotes/inbox/notes & inbox/content]
[Entrypoints] ──────┼──► [CLI / Windows Explorer "Send To" Shortcut]
                    └──► [Local Web UI: FastAPI + Single-Page HTML (Phase 2)]
                                      │
                                      ▼
                    ┌──────────────────────────────────────────┐
                    │        Core Engine (pipeline.py)         │
                    │  1. Audio Ingestion & Settling Check     │
                    │  2. ffmpeg Normalization (16kHz mono)    │
                    │  3. sherpa-onnx STT (+ timestamps)       │
                    │  4. Optional sherpa-onnx Diarization     │
                    │  5. Majority-Overlap Speaker Alignment   │
                    │  6. Transcript Cleanup Pass              │
                    └────────────────────┬─────────────────────┘
                                         │
                                   [Mode Router]
                          ┌──────────────┴──────────────┐
                          ▼                             ▼
                [Notes Structuring]          [Content Structuring]
                (Single-pass LLM)            (Cascade 3-pass chain)
                          │                             │
                          ▼                             ▼
               Local Cache: /output          Local Cache: /output
               (JSON + Markdown)             (JSON + Markdown)
                          │                             │
                          ▼                             ▼
                 Notion DB: Notes              Notion DB: Content
           (Draft + Collapsible Toggle)      (Draft + Local File Ref)
```

**Directory Separation:**
* **Code Repository (`c:\dev\mindnotes`):** Clean source code, tests, and documentation.
* **User Data Directory (`~/Mindnotes/`):**
  * `inbox/notes/` and `inbox/content/<ProjectName>/` (dropped audio files)
  * `processed/` (completed audio files, collision-protected with timestamp suffix)
  * `output/` (persistent JSON and Markdown artifacts with sync metadata)
  * `models/` (downloaded quantized ONNX STT and diarization models)
  * `bin/` (auto-provisioned static `ffmpeg.exe` if not present on system PATH)
  * `config.yaml` and `.env` (user configurations, Notion tokens, LLM keys)

---

## 6. Functional Requirements

### 6.1 Entrypoints, Triggers & Lifecycle

| # | Requirement |
|---|---|
| FR1 | **Watched Folders (v1):** Monitor `~/Mindnotes/inbox/notes` and `~/Mindnotes/inbox/content` using `watchdog`. Support project subfolders (e.g. `inbox/content/LIAS S2/`) to automatically set the `Project` tag, falling back to `default_project` in `config.yaml` if dropped at root. Move completed files to `~/Mindnotes/processed/` with timestamp collision resolution. |
| FR1.1 | **Windows File-Settling & Lock Verification:** Prevent read errors by verifying file size stability ($\ge 2$ seconds unchanged) and acquiring an exclusive read lock before triggering ingestion. |
| FR1.2 | **Dual-Mode Watcher Lifecycle:** Provide a foreground CLI monitor (`mindnotes watch`) with live colored logs, plus a background service installer (`mindnotes autostart enable / disable`) that registers a silent task on Windows login. |
| FR2 | **CLI & Windows Context Menu (v1):** Provide a `typer` CLI (`mindnotes run <file> --mode notes|content`) that integrates with Windows `Send To` for instant right-click processing without open terminal windows. |
| FR3 | **Simple Local Web UI (Phase 2):** Lightweight FastAPI + single-page HTML interface (`localhost`) with drag-and-drop upload, mode toggle, project selector, live progress updates via Server-Sent Events (SSE), and instant auto-push to Notion as `Draft` with an in-browser preview and "Re-sync edits to Notion" capability. |

### 6.2 Lightweight Transcription & Diarization Core

| # | Requirement |
|---|---|
| FR4 | **Audio Normalization:** Transcode input formats (`.mp3`, `.m4a`, `.wav`) to 16kHz mono WAV using `ffmpeg`. If missing on system PATH, `mindnotes setup` auto-provisions a static binary to `~/Mindnotes/bin/`. |
| FR5 | **Quantized ONNX Profiles:** Support downloadable quantized models in `~/Mindnotes/models/`: `fast` (quantized Whisper `small.en` or `Parakeet` ONNX, ~80–150 MB) for Quick Notes, and `accurate` (quantized Whisper `medium.en` / `large-v3-turbo` ONNX, ~250–600 MB) for Content mode. Include `mindnotes setup` to auto-download and verify models. |
| FR6 | Preserve segment timestamps throughout transcription for quote referencing. |
| FR7 | **Native ONNX Diarization (Content Mode):** Use `sherpa-onnx` `OfflineSpeakerDiarization` (Silero VAD + 3d-speaker/WeSpeaker ONNX embeddings). Default to 2 speakers with auto-threshold fallback. Support optional `--speakers "Host,Guest"` CLI/UI flag for human-readable speaker names. |
| FR7.1 | **Majority-Overlap Alignment:** Align Whisper STT segments with diarization turns using time-interval majority overlap to reliably assign speaker labels without CTC alignment bloat. |
| FR8 | 100% Local Inference: Audio, STT, and Diarization execute on CPU with zero data transmitted over network. |
| FR9 | Podcast Scaling: Safely process recordings up to 2 hours using VAD-based chunking without memory exhaustion. |

### 6.3 Mode Router & Structuring

| # | Requirement |
|---|---|
| FR10 | Route modes deterministically via folder origin (`inbox/notes` vs `inbox/content`), CLI flag (`--mode`), or Web UI selection. |
| FR11 | **Vendored LLM Client:** Vendor the provider-agnostic client from `lnchbx-ai-service` into `mindnotes/llm/client.py` with support for Anthropic, OpenAI, Gemini, and DeepSeek via standard env keys. |
| FR12 | **Quick Notes Structuring:** Single fast LLM pass generating: short title, structured body (paragraphs/bullets), and 2–3 suggested tags. |
| FR13 | **Content Mode Cascade Structuring (3-pass chain):**<br>• **Pass 1:** Transcript $\rightarrow$ Episode Title + Show Notes (150–300 words)<br>• **Pass 2:** Transcript $\rightarrow$ 3–5 Pull Quotes with speaker names & `[MM:SS]` timestamps<br>• **Pass 3:** Show Notes + Pull Quotes $\rightarrow$ 3–5 Social Post Ideas (saves $\sim 50\%$ tokens/latency). |

### 6.4 Notion Integration & Resilience

| # | Requirement |
|---|---|
| FR14 | **Schema Pre-Flight Validation:** Provide `mindnotes notion test` to validate API tokens and target database schemas upfront. Gracefully log warnings on missing optional properties rather than failing page creation. |
| FR15 | **Notes DB Push:** Create new page with Title, structured Body, Tags, Source Audio path, Date, Status (`Draft`), and the full verbatim transcript inside a collapsible toggle block (`> Full Transcript`). |
| FR16 | **Content DB Push:** Create new page with Title, Show Notes, Pull Quotes, Social Post Ideas, Source Recording path, Recording Date, Project tag (`LIAS S2`, `Throughline`, `Other`), Status (`Draft`), and a metadata property referencing the local `/output/<id>.md` transcript file. |
| FR17 | **Local-First Caching & Retry (Phase 1):** Save full JSON and Markdown artifacts to `~/Mindnotes/output/<id>.json` *before* attempting Notion sync. Record sync status (`synced: bool`, `notion_page_id`, `error`). Include `mindnotes retry-cached` to sync offline/failed jobs with zero data loss. |

---

## 7. Notion Database Schema

### Notes DB

| Property | Type | Details |
|---|---|---|
| Title | Title | LLM-generated note title |
| Body | Page content (blocks) | Structured draft note (paragraphs & bullet lists) |
| Verbatim Transcript | Page content (toggle block) | `> Full Transcript` containing verbatim text |
| Tags | Multi-select | LLM-suggested, user-editable in Notion |
| Source Audio | Text | Original filename and relative path |
| Created | Date | Creation timestamp |
| Status | Select | `Draft` (default) → `Reviewed` → `Actioned` |

### Content DB

| Property | Type | Details |
|---|---|---|
| Title | Title | Episode / segment title |
| Show Notes | Page content (blocks) | Structured summary (150–300 words) |
| Pull Quotes | Page content (quote blocks) | Speaker attribution + quote + `[MM:SS]` |
| Social Post Ideas | Page content (blocks) | 3–5 short-form draft posts |
| Source Recording | Text | Original filename |
| Local Transcript Path | Text | Absolute path to `~/Mindnotes/output/<id>.md` |
| Recording Date | Date | File metadata date or processing date |
| Project | Select | `LIAS S2` / `Throughline` / `Other` |
| Status | Select | `Draft` (default) → `Ready to post` → `Posted` |

---

## 8. Tech Stack

| Layer | Technology | Details |
|---|---|---|
| **STT & Diarization** | `sherpa-onnx` (ONNX Runtime) | CPU-only wheel (`pip install sherpa-onnx`). Quantized Whisper & Silero VAD / 3d-speaker diarization models. |
| **Audio Normalization** | `ffmpeg` | Transcodes to 16kHz mono WAV. Auto-provisioned in `setup` to `~/Mindnotes/bin/`. |
| **Core & CLI** | Python 3.10+ + `typer` + `watchdog` | Clean CLI commands, file monitoring, and Windows startup management. |
| **LLM Client** | Vendored `mindnotes/llm/client.py` | Provider-agnostic abstraction adapted from `lnchbx-ai-service`. |
| **Notion Integration** | `notion-client` | Official Python SDK with resilient error handling and schema pre-flight. |
| **Storage & Cache** | Local JSON + Markdown | Persisted in `~/Mindnotes/output/` with sync status tracking. |
| **Local Web UI (Phase 2)** | FastAPI + Single-Page HTML/JS | Drag-and-drop upload, SSE live progress, auto-push to Notion with browser edit/re-sync. |

---

## 9. Phased Implementation Roadmap

### Phase 1 — Core Engine, Quick Notes, Watched Folders & Resilience
1. **Repository & Directory Scaffolding:** Set up package structure, `mindnotes setup` (auto-creates `~/Mindnotes` folders, provisions `ffmpeg`, downloads quantized Whisper model).
2. **Audio & STT Engine (`pipeline.py`):** Normalization wrapper + `sherpa-onnx` STT runner + transcript cleanup.
3. **Vendored LLM Client & Notes Structuring:** Embed `client.py`, implement single-pass Quick Notes prompt with toggle transcript formatting.
4. **Local Caching & Notion Writer:** JSON/Markdown output writer with sync tracking, Notion Notes DB writer, and schema validation (`mindnotes notion test`).
5. **CLI & Watcher Daemon:** Implement `mindnotes run`, `mindnotes watch` (with 2s file-settling check), `mindnotes autostart enable/disable`, and `mindnotes retry-cached`.

### Phase 2 — Content Mode, Diarization & Local Web UI
1. **Diarization Engine:** Integrate `sherpa-onnx` `OfflineSpeakerDiarization` with majority-overlap segment alignment and `--speakers` mapping.
2. **Cascade Structuring Chain:** Implement 3-pass sequential LLM workflow for Title/Show Notes, Pull Quotes, and Social Posts.
3. **Notion Content DB Writer:** Content schema writer with local transcript reference.
4. **Subfolder Routing:** Enable `inbox/content/<ProjectName>/` routing in watchdog.
5. **FastAPI Web UI:** Drag-and-drop web dashboard with SSE progress updates and Notion re-sync.

### Phase 3 — Batch Polish & Prompt Tuning
1. Refine prompt templates using real LIAS S2 episodes and daily voice memos.
2. Batch directory import command (`mindnotes batch <dir>`) for backlogs of older recordings.

---

## 10. Success Criteria

* `mindnotes setup` bootstraps directories, checks/provisions `ffmpeg`, and downloads ONNX models in under 5 minutes.
* Voice memo dropped into `~/Mindnotes/inbox/notes` appears in Notion Notes DB within 20 seconds with clean summary and toggle transcript.
* Dropping an audio file while being copied does not crash the pipeline (handled by 2s settling lock check).
* Disconnecting network during processing safely stores output in `~/Mindnotes/output/` and recovers via `mindnotes retry-cached`.
* LIAS S2 podcast audio in Content mode produces speaker-attributed quotes with timestamps and punchy social post drafts.

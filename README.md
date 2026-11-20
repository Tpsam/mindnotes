# Mindnotes

A lightweight speech-to-knowledge pipeline running locally with `sherpa-onnx` and pushing structured output to Notion.

## Features

* **100% Local Inference:** Audio transcription and speaker diarization execute on CPU via `sherpa-onnx` (ONNX Runtime) — zero audio leaves your machine.
* **Dual Modes:**
  * **Quick Notes:** Voice memo $\rightarrow$ first-draft note (title, paragraphs, bullet points, tags) with verbatim transcript in a collapsible toggle.
  * **Content Mode:** Podcast / interview recording $\rightarrow$ title, show notes, pull quotes with timestamps & speaker tags, and social post ideas.
* **Near-Zero Friction Ingestion:**
  * **Watched Folders:** Drop files into `~/Mindnotes/inbox/notes` or `~/Mindnotes/inbox/content`.
  * **Settling Lock Check:** Waits until file write is complete ($\ge 2$s unchanged file size + exclusive read verification) before processing.
  * **Windows Autostart:** Register a silent background task with `mindnotes autostart enable` that starts on Windows login.
* **Notion Integration & Offline Resilience:**
  * Writes structured output and raw transcripts to local cache (`~/Mindnotes/output/`) *before* attempting Notion sync.
  * Recovers offline or failed syncs anytime via `mindnotes retry-cached`.
  * Pre-flight schema validation via `mindnotes notion test`.

---

## Directory Structure

Mindnotes strictly separates source code from user operational data:

* **Repository:** `c:\dev\mindnotes` (clean codebase, tests, docs)
* **User Data:** `~/Mindnotes/` (or configured via `MINDNOTES_HOME`)
  * `inbox/notes/`: Drop voice memos here.
  * `inbox/content/`: Drop podcast recordings here (supports project subfolders, e.g. `LIAS S2/`).
  * `processed/`: Processed audio files moved here automatically.
  * `output/`: Local JSON and Markdown artifacts with Notion sync tracking.
  * `models/`: Downloaded quantized ONNX STT and diarization models.
  * `bin/`: Auto-provisioned static `ffmpeg.exe` if not on system PATH.
  * `config.yaml` & `.env`: Configuration and API keys.

---

## Quickstart

### 1. Create Virtual Environment & Register CLI
Clone the repository and install the package in editable mode (`-e .`), which installs all dependencies and registers the `mindnotes` command in your environment:

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies and register 'mindnotes' command
pip install -e .
```

### 2. Download Local AI Models & FFmpeg
Run the automated setup to bootstrap operational folders in `~/Mindnotes/`, auto-provision FFmpeg, and fetch the quantized local STT models:

```powershell
mindnotes setup
```

*(Optional: Run `mindnotes setup --profile parakeet` if you want the ultra-fast NVIDIA Parakeet model as well).*

### 3. Configure Notion & LLM Keys
Copy `.env.example` to `~/Mindnotes/.env` and add your tokens:

```env
NOTION_API_KEY=ntn_...
NOTION_NOTES_DB_ID=...
NOTION_CONTENT_DB_ID=...

# Set at least one LLM key (DeepSeek, Anthropic, OpenAI, or Gemini):
DEEPSEEK_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...
```

Verify your connection and database columns:
```powershell
mindnotes notion test
```

### 4. Daily Usage

#### Start the watched folder monitor:
```powershell
mindnotes watch
```

#### Process an audio file directly via CLI:
```powershell
mindnotes run "C:\path\to\memo.m4a" --mode notes
```

#### Enable silent background startup on Windows login:
```powershell
mindnotes autostart enable
```

#### Retry unsynced/offline entries:
```powershell
mindnotes retry-cached
```
```bash
python -m mindnotes.cli retry-cached
```

---

## Running Tests

```bash
python -m pytest tests/
```

# AVcleaner

AVcleaner is a local Windows desktop-style web app for cleaning downloaded media
file names before they enter a media library. It focuses on safe local file
renaming, junk-file quarantine, preview, confirmation, execution history, and
rollback.

It intentionally does not scrape metadata, download covers, generate NFO files,
or organize a final media library. Those jobs belong to OpenAver.

## Features

- Local FastAPI + PyWebView architecture.
- Rule-based media code extraction and filename normalization.
- LLM suggestion provider interface for OpenAI-compatible APIs and Ollama.
- Preview-first workflow with conflict and safety validation.
- SQLite run history.
- Quarantine area with rollback instead of permanent deletion.

## Quick Start

```powershell
cd L:\1\AVcleaner
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765` in a browser.

Desktop wrapper:

```powershell
.\.venv\Scripts\python.exe -m avcleaner.desktop
```

## Safety Defaults

- No file is renamed or quarantined during scan or plan generation.
- Execution requires an explicit `confirm: true` API request.
- Existing files are never overwritten.
- Quarantined files are moved under AVcleaner's data directory and can be
  restored through rollback.
- Cloud LLM requests send filenames only by default, not full paths.


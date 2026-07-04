# AVcleaner Packaging

AVcleaner v0.5.0 uses a PyInstaller one-directory portable build first.
Installer packaging is intentionally not mandatory in this phase.

Build from a prepared development environment:

```powershell
cd L:\1\AVcleaner
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\packaging\build_portable.ps1
```

The portable output is:

```text
dist\AVcleaner\
```

The build script adds `portable.flag`, so packaged runtime data is created next
to the executable:

```text
dist\AVcleaner\data
dist\AVcleaner\logs
dist\AVcleaner\quarantine
```

Check the artifact:

```powershell
.\scripts\check_artifact.ps1 .\dist\AVcleaner
```

Run a non-destructive packaged smoke test:

```powershell
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner
```

The package must not include `.venv`, tests, Git metadata, local SQLite user
databases, quarantine contents, logs, or API keys.

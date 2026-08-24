# AVcleaner Packaging

AVcleaner v0.8.2 uses a PyInstaller one-directory portable build first.
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

Run the stronger temp-only execution smoke before publishing:

```powershell
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner -RunTempExecution
```

Create the portable release zip, checksum, and manifest:

```powershell
.\packaging\create_release_zip.ps1 -SmokeTested
.\scripts\check_artifact.ps1 .\release\AVcleaner-v0.8.2-portable-win-x64.zip
.\scripts\smoke_release_zip.ps1 .\release\AVcleaner-v0.8.2-portable-win-x64.zip
```

The package must not include `.venv`, tests, Git metadata, local SQLite user
databases, quarantine contents, logs, or API keys.

For a committed clean rebuild, `artifact-manifest.json` should report
`git_dirty=false`. The dirty check ignores generated `dist/`, `build/`, and
`release/` outputs so rebuilding the artifact does not dirty the manifest by
itself. Actual source changes still make `git_dirty=true`.

PyInstaller may warn that optional hidden imports `pycparser.lextab`,
`pycparser.yacctab`, or `tzdata` were not found. These warnings are documented
as non-blocking for this package because the built executable passes packaged
startup smoke and temp execution smoke. Do not add fragile hidden imports solely
to silence those warnings.

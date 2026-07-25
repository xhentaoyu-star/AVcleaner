# AVcleaner

AVcleaner 是一个面向 Windows 的本地文件清理工具，主要用来处理 BT 下载目录里的脏文件和混乱文件名。
它的目标很明确：在影片进入媒体库、播放器目录或整理目录之前，先把下载包里常见的广告文件、快捷方式、残留说明、可疑小文件、混乱命名和关联字幕文件整理干净。

AVcleaner is a local Windows file-cleaning tool for messy BitTorrent download folders. It helps clean junk files, unsafe leftovers, noisy filenames, and related subtitle files before you move media into a library or player folder.

AVcleaner 不会替你刮削元数据，也不会下载封面、生成 NFO、搬运到最终媒体库；它只专注于“下载目录清理”和“安全改名预览”。

AVcleaner does not scrape metadata, download covers, generate NFO files, or organize a final media library. Its job is the safer step before that: previewing cleanup and rename plans for a download folder.

## 适合用来解决什么问题

BT 下载目录里经常会出现这些东西：

- 文件名带站点广告、发布组水印、无意义前后缀。
- 同一个番号或片名下混着正片、字幕、预览图、说明文件、快捷方式、下载器残留文件。
- `.url`、`.website`、`.txt`、`.nfo`、可疑小文件等不应该进入媒体库的文件。
- 字幕、分段、版本标记和正片之间有关联，但手工整理容易漏掉。
- 批量改名风险高，一旦覆盖、误删或移动错目录，恢复麻烦。

Common problems in BT download folders:

- Filenames polluted by site ads, release tags, watermarks, or meaningless prefixes and suffixes.
- Main videos mixed with subtitles, preview images, notes, shortcuts, and downloader leftovers.
- Junk files such as `.url`, `.website`, `.txt`, `.nfo`, and suspicious tiny files that should not enter a media library.
- Related subtitles and sidecar files that are easy to miss during manual cleanup.
- Risky bulk renames where a wrong move or overwrite is hard to recover from.

AVcleaner 的做法是：先扫描、先生成预览、先让你复核，最后才执行。执行后也会留下历史记录和回滚入口。

AVcleaner works by scanning first, generating a preview first, letting you review the plan first, and only then executing the selected actions. It also keeps execution history and rollback entry points.

## 主要功能

- **扫描下载目录**：读取指定文件夹中的媒体文件、字幕文件和常见下载残留文件。
- **清理脏文件名**：识别番号、分段、字幕语言、版本标记，生成更干净的最终文件名。
- **隔离垃圾文件**：把明显不该进入媒体库的广告、快捷方式、残留文件列为隔离候选，而不是直接删除。
- **安全预览**：扫描和预览不会修改文件；只有点击执行并确认后才会真正改名或隔离。
- **人工复核**：所有建议都会进入表格，你可以选择执行哪些项，也可以手动改最终文件名。
- **阻止高风险操作**：遇到冲突、非法文件名、可能覆盖已有文件等情况，会阻止执行。
- **执行报告**：执行完成后显示成功、跳过、失败、隔离等结果。
- **历史和回滚**：可以查看执行历史；需要恢复时先做回滚预览，再执行回滚。
- **可选 AI 预览**：配置 LLM 后可以让 AI 给出命名建议，但 AI 只改预览结果，不能直接执行文件。
- **本地隐私优先**：默认不把完整本机路径发给云端 LLM；诊断和报告会避免暴露密钥、认证头和原始 LLM 载荷。

Main features:

- **Download folder scanning**: Reads media files, subtitles, and common downloader leftovers.
- **Filename cleanup**: Detects IDs, parts, subtitle language markers, and version tags to build cleaner target names.
- **Junk quarantine**: Marks ads, shortcuts, and leftover files for quarantine instead of deleting them directly.
- **Safe preview**: Scanning and previewing never modify files. Changes happen only after explicit execution and confirmation.
- **Manual review**: Every suggestion appears in a review table. You decide what to execute and can edit final filenames.
- **Risk blocking**: Conflicts, invalid filenames, and possible overwrites are blocked.
- **Execution reports**: Shows renamed, quarantined, skipped, failed, and warning results after execution.
- **History and rollback**: Keeps execution history and supports rollback preview before rollback execution.
- **Optional AI preview**: LLM suggestions can improve preview names, but cannot execute file operations.
- **Local privacy first**: Full local paths are not sent to cloud LLM providers by default, and diagnostics avoid secrets and raw LLM payloads.

## 安全边界

AVcleaner 的核心原则是“不预览就不执行，不确认就不改文件”。

- 扫描不会改名、移动、删除或隔离文件。
- 预览只生成计划，不会修改磁盘。
- 执行必须使用后端保存的计划、选中项和 `plan_hash`。
- 前端传来的本机路径不会被执行接口信任。
- 已存在文件不会被覆盖。
- 隔离不是永久删除，后续可以通过历史记录回滚。
- 回滚也不会覆盖已有文件。
- 旧的通用执行接口 `/api/execute` 保持禁用。
- 旧的通用 LLM 建议接口 `/api/llm/suggest` 保持禁用。
- AI 建议必须通过结构校验和文件名安全校验，不能绕过规则。

Safety boundaries:

- Scanning never renames, moves, deletes, or quarantines files.
- Previewing only creates a plan and does not write to disk.
- Execution requires the server-side saved plan, selected item IDs, and `plan_hash`.
- Frontend-supplied local paths are not trusted by the execution endpoint.
- Existing files are never overwritten.
- Quarantine is reversible through execution history.
- Rollback also refuses to overwrite existing files.
- The legacy generic `/api/execute` endpoint stays disabled.
- The legacy generic `/api/llm/suggest` endpoint stays disabled.
- AI suggestions must pass structured validation and filename safety validation.

## 它不做什么

AVcleaner 不是媒体库管理器，也不是刮削器。它不会：

- 刮削影片元数据。
- 下载封面。
- 生成 NFO。
- 按演员、片商、分类建立最终媒体库结构。
- 把文件搬进 Jellyfin、Emby、Plex 或其他最终媒体库目录。
- 接入 OpenAver 数据库。

AVcleaner is not a media-library manager or metadata scraper. It does not:

- Scrape movie metadata.
- Download cover images.
- Generate NFO files.
- Build actor, studio, or category-based final library structures.
- Move files into Jellyfin, Emby, Plex, or another final media-library folder.
- Integrate with an OpenAver database.

如果你需要的是“把 BT 下载目录先清理干净”，AVcleaner 是这个环节的工具；如果你需要的是完整媒体库管理，它应该放在 AVcleaner 之后。

If your need is to clean a BT download folder before library import, AVcleaner fits that step. If you need full media-library management, use a separate tool after AVcleaner.

## 快速开始

1. 到 GitHub Releases 下载最新便携版 `AVcleaner-v0.8.1-portable-win-x64.zip`。
2. 解压到你希望保存软件的位置，例如 `D:\Tools\AVcleaner`。
3. 双击运行 `AVcleaner.exe`。
4. 在工作台选择 BT 下载目录。
5. 点击“分析”，生成预览。
6. 检查表格里的“原文件”和“最终文件名”。
7. 只勾选你确认要处理的项目。
8. 查看执行摘要。
9. 点击“执行选中”，再次确认后才会真正改名或隔离。

Quick start:

1. Download the latest portable build from GitHub Releases: `AVcleaner-v0.8.1-portable-win-x64.zip`.
2. Extract it to a stable folder, for example `D:\Tools\AVcleaner`.
3. Run `AVcleaner.exe`.
4. Choose a BT download folder in the workbench.
5. Click Analyze to generate a preview.
6. Review the original filenames and final filenames.
7. Select only the items you want to process.
8. Check the execution summary.
9. Click Execute Selected and confirm before any real rename or quarantine happens.

如果执行结果不符合预期，到“历史”里查看记录，先做回滚预览，再执行回滚。

If the result is not what you expected, open History, run a rollback preview first, and only then execute the rollback.

## 日常使用流程

### 1. 选择下载目录

选择一个 BT 下载完成后的目录。AVcleaner 会把这个目录当成待清理区域。

Choose a completed BT download folder. AVcleaner treats this folder as the cleanup target.

### 2. 生成预览

默认使用规则预览。规则预览适合大多数标准番号、分段、字幕语言和常见脏后缀。

The default mode is rule-based preview, which works for most common IDs, parts, subtitle language markers, and noisy suffixes.

如果你已经配置 LLM，界面会出现 AI 智能预览。AI 只提供建议，仍然要经过 AVcleaner 的结构校验、文件名校验和人工复核。

If an LLM is configured, AI Preview becomes available. AI suggestions still go through AVcleaner validation and manual review.

### 3. 复核结果

重点看三列：

- **原文件**：当前下载目录里的文件。
- **最终文件名**：AVcleaner 建议变成的名字，可以手动修改。
- **状态/提示**：是否可执行、是否有警告、是否被阻止。

Focus on three columns:

- **Original file**: The current file in the download folder.
- **Final filename**: The suggested target name, which you can edit.
- **Status / notes**: Whether the item can be executed, has warnings, or is blocked.

### 4. 执行选中项

不要无脑全选。先选安全项，再检查警告项。执行前会显示摘要，确认后才会落盘。

Do not blindly select everything. Select safe items first, review warnings, and confirm the execution summary before writing changes to disk.

### 5. 查看报告和历史

执行完成后可以看报告。如果需要撤回，到历史记录里做回滚预览。回滚预览通过后，再执行回滚。

After execution, review the report. If you need to undo changes, use rollback preview from History before executing rollback.

## 文件会被放到哪里

便携版旁边会有这些运行目录：

- `data`：本地数据库和状态。
- `logs`：日志。
- `quarantine`：默认隔离目录。

The portable build may create these local runtime folders beside the app:

- `data`: Local database and state.
- `logs`: Logs.
- `quarantine`: Default quarantine folder.

如果你在设置里配置了隔离目录，隔离文件会进入你指定的位置。建议不要把隔离目录设到最终媒体库里。

If you configure a custom quarantine folder, quarantined files go there. Do not place the quarantine folder inside the final media library.

## AI 预览说明

AI 预览是可选功能，不配置也能正常使用规则预览。

AI Preview is optional. Rule-based preview works without any LLM configuration.

AI 预览的限制：

- AI 不能直接改名、移动、删除或隔离文件。
- AI 只能修改预览计划里的最终文件名。
- AI 输出必须符合固定结构。
- AI 建议仍然要经过文件名安全校验。
- 默认不会把完整本机路径发给云端 LLM。
- 手动修改优先于 AI 建议。

AI Preview limits:

- AI cannot directly rename, move, delete, or quarantine files.
- AI can only adjust final filenames inside the preview plan.
- AI output must match the required structure.
- AI suggestions still pass filename safety validation.
- Full local paths are not sent to cloud LLM providers by default.
- Manual edits override AI suggestions.

## 从源码运行

普通用户建议直接下载 Releases 里的便携版。下面是开发者从源码运行的方式：

Regular users should download the portable release. The following commands are for developers running from source:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8765
```

桌面窗口模式：

Desktop window mode:

```powershell
.\.venv\Scripts\python.exe -m avcleaner.desktop
```

开发检查：

Development checks:

```powershell
.\scripts\check.ps1
```

开发时请使用项目虚拟环境里的 Python，或者使用上面的脚本；不要用系统里的 bare python 直接跑检查，避免多个 Python 环境导致依赖不一致。

During development, use the project virtual environment or the scripts above. Do not run checks with system-level bare python, because multiple Python installations can produce inconsistent dependencies.

带打包检查：

Checks including packaging:

```powershell
.\scripts\check.ps1 -WithPackaging
```

## 当前状态

- 平台：Windows 优先。
- 主要形态：本地桌面工具 / 本地 Web UI。
- 前端：Jinja2 模板、静态 CSS、静态 `app.js`。
- 后端：FastAPI。
- 当前版本：`0.8.1`。

Current status:

- Platform: Windows first.
- Form: Local desktop tool / local Web UI.
- Frontend: Jinja2 templates, static CSS, static `app.js`.
- Backend: FastAPI.
- Version: `0.8.1`.

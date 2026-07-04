# AVcleaner v0.6.1 快速开始

AVcleaner 是本机文件名复核工具。扫描和生成预览不会改名、隔离或删除文件。
只有点击执行选中并确认后，文件才会变化。

## 基本流程

1. 选择文件夹。
2. 扫描。
3. 生成预览。
4. 复核表格。阻止项不能执行，警告项需要检查。
5. 选择安全项，或只手动勾选你确认过的行。
6. 查看执行摘要。
7. 执行选中。
8. 需要时从历史记录回滚。

隔离不是永久删除，可通过回滚恢复。大文件隔离可能耗时，但仍按同一套安全
流程执行。

## LLM suggestions

LLM 面板默认折叠，只在已有预览后使用。

Compatibility mode does not bypass validation. LLM suggestions are never
auto-selected, never auto-applied, and never execute files. By default AVcleaner
sends filename-level data only, not full local paths.

可选模式：

- Strict OpenAI JSON Schema: 用于真正支持 `response_format=json_schema` 的供应商。
- Prompt JSON compatibility: 用于自称 OpenAI 兼容但不支持严格 schema 的网关。
- Claude gateway compatibility: 用于 Claude/Anthropic 风格中间层。
- Ollama: 本地 Ollama JSON mode。

## 便携 zip

解压 `AVcleaner-v0.6.1-portable-win-x64.zip` 后运行 `AVcleaner.exe`。
有 `portable.flag` 时，数据保存在程序旁边的 `data`、`logs`、`quarantine`。
没有便携标记时，Windows 默认使用 `%LOCALAPPDATA%\AVcleaner`。

发布包旁边的 `.sha256` 文件可用于核对 SHA256。

## What AVcleaner does not do

AVcleaner does not scrape metadata, download covers, generate NFO files, move
files into the final media library, or replace OpenAver.

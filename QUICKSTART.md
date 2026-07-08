# AVcleaner 快速开始 / Quick Start

这份文档是给普通使用者看的，不需要懂代码。

This guide is for regular users. No coding knowledge is required.

AVcleaner 用来清理 BT 下载目录里的脏文件和混乱命名。它会先生成预览，让你确认哪些文件要改名、哪些垃圾文件要隔离；只有你点击“执行选中”并再次确认后，才会真正修改文件。

AVcleaner cleans messy BT download folders. It generates a preview first, lets you confirm which files should be renamed or quarantined, and only modifies files after you click Execute Selected and confirm.

## 下载安装 / Download And Install

1. 打开项目的 GitHub Releases 页面。
2. 下载最新版本 `AVcleaner-v0.8.0-portable-win-x64.zip`。
3. 解压到一个固定目录，例如 `D:\Tools\AVcleaner`。
4. 双击 `AVcleaner.exe` 启动。

1. Open the project GitHub Releases page.
2. Download the latest `AVcleaner-v0.8.0-portable-win-x64.zip`.
3. Extract it to a stable folder, for example `D:\Tools\AVcleaner`.
4. Run `AVcleaner.exe`.

不要把压缩包直接放在下载目录里运行。建议先解压到固定工具目录，再用它处理你的 BT 下载目录。

Do not run the app directly from the download folder or inside the zip file. Extract it to a stable tools folder first, then use it to process BT download folders.

## 第一次使用 / First Use

1. 点击“选择文件夹”，选择一个 BT 下载完成后的文件夹。
2. 保持默认的“规则预览”。
3. 点击“分析”。
4. 等待表格出现预览结果。
5. 逐项检查“原文件”和“最终文件名”。
6. 勾选确认要处理的项目。
7. 点击“执行摘要”，确认将要改名、隔离或跳过的数量。
8. 点击“执行选中”，再次确认。
9. 执行完成后查看报告。

1. Click Choose Folder and select a completed BT download folder.
2. Keep the default Rule Preview mode.
3. Click Analyze.
4. Wait for the preview table.
5. Review Original File and Final Filename row by row.
6. Select the items you want to process.
7. Open the execution summary and confirm the rename, quarantine, and skip counts.
8. Click Execute Selected and confirm again.
9. Review the report after execution.

## 你应该重点看什么 / What To Check

- **原文件**：下载目录里的当前文件。
- **最终文件名**：AVcleaner 建议的新名字。
- **状态**：能不能执行，有没有阻止项。
- **提示**：是否需要人工复核。
- **执行摘要**：真正落盘前的最后确认。

- **Original file**: The current file in the download folder.
- **Final filename**: The new name suggested by AVcleaner.
- **Status**: Whether the item can be executed or is blocked.
- **Notes**: Whether manual review is needed.
- **Execution summary**: The final check before writing changes to disk.

如果你不确定某一项，先不要勾选它。

If you are unsure about an item, leave it unselected.

## 隔离是什么意思 / What Quarantine Means

隔离不是永久删除。

Quarantine is not permanent deletion.

AVcleaner 会把广告、快捷方式、下载残留文件等移动到隔离目录。这样它们不会进入媒体库，但后续仍然可以通过历史记录回滚。

AVcleaner moves ads, shortcuts, downloader leftovers, and similar junk files into a quarantine folder. They stay out of your media library, but can still be rolled back from History.

默认隔离目录在 AVcleaner 自己的运行目录里。你也可以在设置里改成其他目录。

The default quarantine folder is inside AVcleaner’s runtime folder. You can change it in Settings.

## 如何恢复 / How To Restore

1. 打开“历史”。
2. 选择一次执行记录。
3. 先点击“回滚预览”。
4. 确认不会覆盖已有文件。
5. 再执行回滚。

1. Open History.
2. Select an execution record.
3. Click Rollback Preview first.
4. Confirm that existing files will not be overwritten.
5. Execute the rollback.

回滚也不会覆盖目标位置已经存在的文件。

Rollback also refuses to overwrite existing files.

## AI 智能预览 / AI Preview

AI 智能预览是可选功能，不配置也能使用 AVcleaner。

AI Preview is optional. AVcleaner works without it.

如果你配置了 LLM，界面会显示 AI 智能预览。它只会给出命名建议，不会直接执行文件操作。所有 AI 建议仍然必须通过 AVcleaner 的安全校验。

If you configure an LLM, AI Preview becomes available. It only suggests filenames and never directly performs file operations. All AI suggestions still go through AVcleaner safety validation.

默认情况下，AVcleaner 不会把完整本机路径发送给云端 LLM。

By default, AVcleaner does not send full local paths to cloud LLM providers.

## AVcleaner 不做什么 / What AVcleaner Does Not Do

AVcleaner 不负责完整媒体库管理。

AVcleaner is not a full media-library manager.

它不会：

- 刮削影片信息。
- 下载封面。
- 生成 NFO。
- 把文件移动到最终媒体库。
- 按演员、片商、分类整理目录。
- 接入 OpenAver 数据库。

It does not:

- Scrape movie metadata.
- Download cover images.
- Generate NFO files.
- Move files into the final media library.
- Organize folders by actor, studio, or category.
- Integrate with an OpenAver database.

它的定位是：在你把 BT 下载内容放进媒体库之前，先安全地清理脏文件和脏文件名。

Its job is to safely clean junk files and messy filenames before you import BT downloads into a media library.

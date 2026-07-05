const state = {
  capabilities: null,
  settings: null,
  folderPickerState: null,
  scan: null,
  plan: null,
  llmSuggestions: [],
  previewMode: "rule",
  settingsTab: "llm",
  filter: "all",
  runFilter: "all",
  loading: "",
  busy: {},
  rowSaving: {},
  detailItemId: "",
  feedbackTimer: null,
  lastStatus: { message: "待命", type: "info" },
  executionSummary: null,
  executionReport: null,
  diagnostics: null,
  runs: [],
  selectedRun: null,
  rollbackPreview: null,
  recentFolders: [],
};

const PLAN_TABLE_COLS = 7;
const $ = (selector) => document.querySelector(selector);
const apiToken = document.querySelector('meta[name="avcleaner-token"]')?.content || "";
const FEEDBACK_TYPES = new Set(["info", "success", "warning", "error", "loading"]);

const SECRET_PATTERNS = [
  /Authorization\s*[:=]\s*[^\s,;]+/gi,
  /X-AVCleaner-Token\s*[:=]\s*[^\s,;]+/gi,
  /api[_-]?key\s*[:=]\s*[^\s,;]+/gi,
  /Bearer\s+[A-Za-z0-9._-]+/gi,
  /sk-[A-Za-z0-9_-]{8,}/g,
  /[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*/g,
];

const BUSY_KEYS = [
  "analyzing",
  "validating",
  "requestingAi",
  "savingEdit",
  "updatingSelection",
  "exporting",
  "executing",
  "rollingBack",
  "loadingHistory",
  "loadingDiagnostics",
];

const ACTION_LABELS = {
  "rename": "改名",
  "quarantine": "隔离",
  "review": "复核",
  "keep": "保留",
  "skip": "跳过",
};

const SOURCE_LABELS = {
  "rule": "规则",
  "llm": "AI",
  "manual": "手动",
  "rule_fallback": "规则回退",
};

const LLM_STATE_LABELS = {
  hidden: "",
  not_requested: "",
  not_configured: "未配置",
  requesting: "请求中",
  applied_to_preview: "AI",
  valid_but_not_used: "保留手动",
  invalid: "无效",
  schema_error: "格式错误",
  safety_error: "安全拒绝",
  provider_error: "供应商错误",
  stale: "已过期",
};

const STATUS_LABELS = {
  "ok": "可处理",
  "selected": "已选",
  "blocking": "阻止",
  "warning": "警告",
  "requires_review": "需复核",
  "conflict": "冲突",
  "sidecar": "关联文件",
  "junk_candidate": "垃圾候选",
  "manual_edited": "手动修改",
};

const SELECTION_LOCK_EXPLANATIONS = {
  "blocking": {
    title: "被阻止",
    explanation: "这一项有阻止级问题，前端不会允许选择，后端也会拒绝执行。",
    suggested_action: "先修改建议文件名或跳过这一项。",
  },
  "not_executable": {
    title: "不是可执行动作",
    explanation: "保留、复核、跳过这类状态不会直接改动文件。",
    suggested_action: "如需处理，请先把目标文件名改成明确的改名建议。",
  },
  "sidecar_default_off": {
    title: "关联文件默认不选",
    explanation: "字幕、图片、NFO 等关联文件只显示建议，默认不自动执行。",
    suggested_action: "确认和主视频匹配后再手动勾选。",
  },
};

const CODE_EXPLANATIONS = {
  "case_only_rename": {
    title: "仅大小写变化",
    explanation: "Windows 通常不区分大小写，AVcleaner 执行时会用临时文件名完成安全的两段式改名。",
    suggested_action: "通常可以执行；如无必要也可以跳过。",
  },
  "target_exists": {
    title: "目标已存在",
    explanation: "目标文件名已经存在，AVcleaner 不会覆盖已有文件。",
    suggested_action: "请手动修改建议文件名，或取消选择这一项。",
  },
  "target_exists_case_insensitive": {
    title: "目标大小写冲突",
    explanation: "同目录里已有一个只在大小写上不同的目标名，Windows 下会冲突。",
    suggested_action: "请换一个明确不同的文件名。",
  },
  "duplicate_target": {
    title: "多个项目指向同一目标",
    explanation: "预览中至少两项会改成同一个文件名。",
    suggested_action: "保留一个，其他项手动改名或取消选择。",
  },
  "duplicate_target_case_insensitive": {
    title: "多个项目大小写冲突",
    explanation: "多个目标名只在大小写上不同，Windows 下仍然冲突。",
    suggested_action: "请给其中一项改成明确不同的名字。",
  },
  "path_escape": {
    title: "目标路径越界",
    explanation: "目标位置不在当前扫描文件夹内，AVcleaner 不会执行。",
    suggested_action: "只编辑文件名，不要输入路径。",
  },
  "extension_changed": {
    title: "扩展名变化",
    explanation: "建议结果改变了扩展名，这可能破坏文件类型。",
    suggested_action: "改回原扩展名，或跳过这一项。",
  },
  "empty_name": {
    title: "文件名为空",
    explanation: "目标文件名不能为空。",
    suggested_action: "输入有效文件名。",
  },
  "invalid_character": {
    title: "非法字符",
    explanation: "目标文件名包含 Windows 不允许的字符。",
    suggested_action: "删除斜杠、冒号、星号、问号、引号、尖括号或竖线。",
  },
  "control_character": {
    title: "控制字符",
    explanation: "目标文件名包含不可见控制字符。",
    suggested_action: "重新输入文件名，不要复制不可见字符。",
  },
  "trailing_dot_or_space": {
    title: "末尾点或空格",
    explanation: "Windows 不可靠地处理末尾是点或空格的文件名。",
    suggested_action: "删除文件名末尾的点或空格。",
  },
  "reserved_name": {
    title: "系统保留名",
    explanation: "目标名使用了 CON、PRN、AUX 等 Windows 保留名称。",
    suggested_action: "换一个普通文件名。",
  },
  "reserved_name_with_extension": {
    title: "系统保留名带扩展名",
    explanation: "即使带扩展名，Windows 仍会把这个名字视为保留名。",
    suggested_action: "换一个普通文件名。",
  },
  "alternate_data_stream": {
    title: "疑似 ADS 文件名",
    explanation: "文件名中包含冒号，可能触发 Windows 备用数据流语义。",
    suggested_action: "删除冒号。",
  },
  "source_missing": {
    title: "源文件不存在",
    explanation: "预览后源文件被移动、删除，或扫描结果已过期。",
    suggested_action: "重新扫描并生成预览。",
  },
  "source_changed": {
    title: "源文件已变化",
    explanation: "预览后源文件大小或时间戳发生变化，不能按旧计划执行。",
    suggested_action: "重新扫描并生成预览。",
  },
  "path_too_long": {
    title: "路径过长",
    explanation: "目标完整路径超过当前安全限制。",
    suggested_action: "缩短文件夹路径或目标文件名。",
  },
  "path_near_limit": {
    title: "路径接近上限",
    explanation: "目标路径接近 Windows 传统长度限制，后续移动可能有风险。",
    suggested_action: "建议缩短文件名或上级文件夹名。",
  },
  "target_same_as_source": {
    title: "目标与源相同",
    explanation: "建议结果没有实际改名动作。",
    suggested_action: "通常可以跳过。",
  },
  "restore_target_exists": {
    title: "回滚目标已存在",
    explanation: "回滚位置已有文件，AVcleaner 不会覆盖。",
    suggested_action: "先手动处理冲突文件，再回滚。",
  },
  "run_not_found": {
    title: "批次不存在",
    explanation: "本地数据库里找不到这个执行批次。",
    suggested_action: "刷新历史记录后重试。",
  },
  "rollback_not_available": {
    title: "不可回滚",
    explanation: "这个批次没有可回滚的改名或隔离项。",
    suggested_action: "查看批次详情确认执行项状态。",
  },
  "rollback_target_exists": {
    title: "回滚目标已存在",
    explanation: "原位置已经有文件，回滚不会覆盖它。",
    suggested_action: "先处理原位置冲突文件，再重新预览回滚。",
  },
  "rollback_source_missing": {
    title: "回滚来源缺失",
    explanation: "执行后的文件已经不在预期位置，无法安全改回。",
    suggested_action: "确认文件是否被其他工具移动或删除。",
  },
  "quarantine_file_missing": {
    title: "隔离文件缺失",
    explanation: "隔离区里的文件不存在，无法恢复。",
    suggested_action: "检查隔离目录或保留该项为失败记录。",
  },
  "rollback_file_changed": {
    title: "文件已变化",
    explanation: "执行后的文件大小或修改时间与执行快照不一致。",
    suggested_action: "先确认这个文件是否仍是原文件，再决定是否手动处理。",
  },
  "unknown_run_item": {
    title: "批次项目不存在",
    explanation: "请求里包含这个批次没有的项目 ID。",
    suggested_action: "刷新批次详情后重试。",
  },
  "rollback_already_completed": {
    title: "已经回滚",
    explanation: "这个项目已经完成过回滚，不会重复执行。",
    suggested_action: "刷新历史详情查看当前状态。",
  },
  "unknown_selected_item_ids": {
    title: "选择项不存在",
    explanation: "请求里包含当前计划没有的项目 ID。",
    suggested_action: "刷新预览后重试。",
  },
  "unknown_plan_item": {
    title: "计划项不存在",
    explanation: "要修改或选择的项目不在当前计划里。",
    suggested_action: "刷新预览后重试。",
  },
  "blocking_item_selected": {
    title: "选择了阻止项",
    explanation: "选中项目里包含阻止级问题，不能执行。",
    suggested_action: "取消阻止项，或先修正文件名。",
  },
  "invalid_target_name": {
    title: "目标文件名无效",
    explanation: "手动输入的目标文件名没有通过 Windows 文件名校验。",
    suggested_action: "按提示修改目标文件名。",
  },
  "path_separator_in_target": {
    title: "目标名包含路径分隔符",
    explanation: "手动编辑只允许文件名，不允许输入文件夹路径。",
    suggested_action: "删除斜杠或反斜杠。",
  },
  "no_selected_items": {
    title: "没有选中项目",
    explanation: "执行需要至少一个已选中的改名或隔离项。",
    suggested_action: "选择安全项，或手动勾选要执行的项目。",
  },
  "api_token_missing": {
    title: "缺少本地令牌",
    explanation: "这个接口需要 GUI 启动时注入的本地访问令牌。",
    suggested_action: "刷新页面；如果仍失败，请重新启动 AVcleaner。",
  },
  "api_token_invalid": {
    title: "本地令牌无效",
    explanation: "页面里的本地访问令牌和当前服务不匹配。",
    suggested_action: "刷新页面；如果仍失败，请重新启动 AVcleaner。",
  },
  "plan_hash_mismatch": {
    title: "预览已变化",
    explanation: "当前计划哈希和执行摘要不一致，说明预览或选择状态已经变化。",
    suggested_action: "重新校验并重新查看执行摘要。",
  },
  "legacy_execute_disabled": {
    title: "旧执行接口已禁用",
    explanation: "AVcleaner 不再接受前端直接提交文件路径执行。",
    suggested_action: "使用当前预览计划里的执行选中按钮。",
  },
  "request_extra_fields": {
    title: "请求包含多余字段",
    explanation: "后端拒绝未声明字段，避免前端绕过安全模型。",
    suggested_action: "刷新页面后重试。",
  },
  "llm_auth_failed": {
    title: "LLM 认证失败",
    explanation: "供应商拒绝了当前密钥或认证信息。",
    suggested_action: "检查设置里的供应商、Base URL、模型和密钥。",
  },
  "llm_request_failed": {
    title: "LLM 请求失败",
    explanation: "LLM 服务返回错误或网络请求失败。",
    suggested_action: "检查服务地址、网络连接和供应商状态。",
  },
  "llm_schema_invalid": {
    title: "LLM Schema 不兼容",
    explanation: "供应商不支持严格 JSON Schema，或返回格式与严格模式不兼容。",
    suggested_action: "改用 Prompt JSON 兼容或 Claude gateway 兼容模式。",
  },
  "llm_not_configured": {
    title: "LLM 未配置",
    explanation: "当前没有启用可用的 LLM 供应商或模型。",
    suggested_action: "在设置里选择供应商并填写模型信息，或继续只用规则建议。",
  },
  "llm_provider_error": {
    title: "LLM 供应商错误",
    explanation: "供应商返回了无法归类的错误。",
    suggested_action: "查看测试结果，必要时切换兼容模式。",
  },
  "llm_timeout": {
    title: "LLM 超时",
    explanation: "LLM 请求没有在限定时间内完成。",
    suggested_action: "减少一次请求的项目数，或检查本地/远程模型速度。",
  },
  "llm_invalid_json": {
    title: "LLM 返回的 JSON 无效",
    explanation: "兼容模式可以提取 JSON，但不能修复语法错误。",
    suggested_action: "换兼容模式、降低温度，或修改供应商设置。",
  },
  "llm_no_json_object": {
    title: "LLM 没有返回 JSON 对象",
    explanation: "返回内容里没有可解析的 JSON 对象。",
    suggested_action: "使用 Prompt JSON 兼容模式，或换一个更稳定的模型。",
  },
  "llm_multiple_json_objects": {
    title: "LLM 返回多个 JSON 对象",
    explanation: "结果中出现多个对象，AVcleaner 无法确定采用哪个。",
    suggested_action: "要求模型只返回一个 JSON 对象。",
  },
  "llm_missing_required_field": {
    title: "LLM 缺少必填字段",
    explanation: "建议缺少 item_id、suggested_name、confidence 等必需字段。",
    suggested_action: "换兼容模式或调整模型。",
  },
  "llm_extra_field": {
    title: "LLM 返回多余字段",
    explanation: "严格输出不接受未声明字段。",
    suggested_action: "继续使用当前安全校验，必要时换模型。",
  },
  "llm_wrong_field_type": {
    title: "LLM 字段类型错误",
    explanation: "LLM 把数字、字符串、数组等类型返回错了。",
    suggested_action: "换兼容模式或降低温度。",
  },
  "llm_confidence_out_of_range": {
    title: "LLM 置信度越界",
    explanation: "confidence 必须在 0 到 1 之间。",
    suggested_action: "忽略这条建议，或换模型重试。",
  },
  "llm_suggestion_invalid": {
    title: "LLM 建议无效",
    explanation: "LLM 建议没有通过规范化、Pydantic 或文件名校验。",
    suggested_action: "不要接受这条建议；可手动编辑目标文件名。",
  },
  "llm_path_like_suggestion": {
    title: "LLM 建议像路径",
    explanation: "LLM 返回了包含文件夹路径的建议名。",
    suggested_action: "AVcleaner 已拒绝；只能接受文件名。",
  },
  "llm_extension_changed": {
    title: "LLM 改了扩展名",
    explanation: "LLM 建议改变了原始扩展名。",
    suggested_action: "AVcleaner 已拒绝；如需处理请手动改回原扩展名。",
  },
  "llm_reserved_name": {
    title: "LLM 使用保留名",
    explanation: "LLM 建议命中了 Windows 保留名称。",
    suggested_action: "不要接受这条建议。",
  },
  "llm_invalid_windows_name": {
    title: "LLM 文件名不合法",
    explanation: "LLM 建议没有通过 Windows 文件名规则。",
    suggested_action: "不要接受这条建议。",
  },
  "llm_target_conflict": {
    title: "LLM 目标冲突",
    explanation: "LLM 建议会和现有文件或计划内目标冲突。",
    suggested_action: "不要接受这条建议，或手动改名。",
  },
  "llm_payload_privacy_violation": {
    title: "LLM 载荷隐私检查失败",
    explanation: "准备发送给 LLM 的内容触发了隐私边界。",
    suggested_action: "保持默认只发送文件名，关闭完整路径发送。",
  },
  "llm_cache_error": {
    title: "LLM 缓存错误",
    explanation: "读取或写入建议缓存失败，但不会影响文件安全。",
    suggested_action: "可以重试，或忽略缓存继续手动处理。",
  },
  "legacy_llm_suggest_disabled": {
    title: "旧 LLM 接口已禁用",
    explanation: "通用 LLM 建议接口已关闭，避免绕过计划级审查。",
    suggested_action: "使用当前计划下的 LLM 建议按钮。",
  },
  "suggestion_not_found": {
    title: "建议不存在",
    explanation: "要接受或拒绝的 LLM 建议不存在。",
    suggested_action: "刷新建议列表后重试。",
  },
  "suggestion_plan_mismatch": {
    title: "建议不属于当前计划",
    explanation: "这条 LLM 建议和当前计划不匹配。",
    suggested_action: "重新生成建议。",
  },
  "suggestion_stale": {
    title: "建议已过期",
    explanation: "计划被重新校验、编辑或选择后，旧建议不能直接接受。",
    suggested_action: "重新请求 LLM 建议。",
  },
  "suggestion_validation_failed": {
    title: "建议校验失败",
    explanation: "接受建议前的后端校验失败。",
    suggested_action: "不要接受这条建议，或手动编辑。",
  },
  "blocking_suggestion": {
    title: "建议会造成阻止项",
    explanation: "LLM 建议会引入阻止级问题。",
    suggested_action: "不要接受这条建议。",
  },
  "manual_edit_conflict": {
    title: "与手动修改冲突",
    explanation: "这一项已经被手动编辑，旧 LLM 建议不能覆盖人工决定。",
    suggested_action: "保留手动结果，或重新请求建议。",
  },
  "low_confidence": {
    title: "置信度偏低",
    explanation: "规则识别结果低于复核阈值。",
    suggested_action: "人工确认番号和目标名后再选择。",
  },
  "media_code_not_detected": {
    title: "未识别番号",
    explanation: "规则没有可靠识别出媒体番号。",
    suggested_action: "手动改名，或使用 LLM 建议辅助判断。",
  },
  "detected_media_code": {
    title: "已识别番号",
    explanation: "规则识别出媒体番号并生成了目标文件名。",
    suggested_action: "核对无误后可以执行。",
  },
  "kept": {
    title: "保持原样",
    explanation: "这一项没有触发改名或隔离规则。",
    suggested_action: "通常不需要处理。",
  },
  "already_clean": {
    title: "已经干净",
    explanation: "文件名已经符合当前规则。",
    suggested_action: "不需要执行。",
  },
  "sidecar_suggested_rename": {
    title: "关联文件建议改名",
    explanation: "这是字幕、图片或 NFO 等关联文件建议，默认不选中。",
    suggested_action: "确认它属于同一番号后再手动勾选。",
  },
  "sidecar_already_clean": {
    title: "关联文件已干净",
    explanation: "关联文件名已经符合当前规则。",
    suggested_action: "不需要执行。",
  },
  "sidecar_unmatched": {
    title: "关联文件未匹配",
    explanation: "关联文件没有识别出可匹配的番号。",
    suggested_action: "通常跳过，必要时手动处理。",
  },
  "image_default_off": {
    title: "图片关联文件默认不执行",
    explanation: "图片可能是截图、封面或临时文件，AVcleaner 只展示建议。",
    suggested_action: "确认用途后再手动勾选。",
  },
  "nfo_default_off": {
    title: "NFO 关联文件默认不执行",
    explanation: "NFO 可能被其他工具使用，AVcleaner 不默认改名。",
    suggested_action: "确认不会影响其他工具后再手动勾选。",
  },
  "subtitle_sidecar": {
    title: "字幕关联文件",
    explanation: "字幕会尽量保留语言后缀，例如 .zh.srt 或 .chs.ass。",
    suggested_action: "确认和视频匹配后再选择。",
  },
  "sidecar_default_off": {
    title: "关联文件默认关闭",
    explanation: "关联文件建议默认不执行，避免误改配套文件。",
    suggested_action: "确认后手动勾选。",
  },
  "not_executable": {
    title: "当前动作不可执行",
    explanation: "这一项只是保留或复核状态，不会直接改动文件。",
    suggested_action: "需要处理时先手动编辑目标名。",
  },
  "plan_not_validated": {
    title: "预览需要重新校验",
    explanation: "计划状态已变化，执行前必须重新校验。",
    suggested_action: "点击重新校验。",
  },
  "plan_hash_missing": {
    title: "缺少预览哈希",
    explanation: "当前预览没有可用于执行校验的 plan_hash。",
    suggested_action: "重新生成预览。",
  },
  "plan_hash_mismatch_local": {
    title: "执行摘要已过期",
    explanation: "上次执行摘要对应的预览已经变化。",
    suggested_action: "重新查看执行摘要。",
  },
  "no_plan": {
    title: "未生成预览",
    explanation: "执行必须基于后端保存的预览计划。",
    suggested_action: "先扫描并生成预览。",
  },
  "validation_error": {
    title: "请求校验失败",
    explanation: "请求内容没有通过接口结构校验。",
    suggested_action: "刷新页面后重试；如果仍失败，请保存诊断信息。",
  },
  "root_required": {
    title: "需要选择文件夹",
    explanation: "扫描前必须填写要处理的文件夹。",
    suggested_action: "先选择或输入文件夹路径。",
  },
  "filename_required": {
    title: "需要输入文件名",
    explanation: "规则测试需要一个样例文件名。",
    suggested_action: "输入一个文件名后再测试。",
  },
  "settings_import_required": {
    title: "需要导入内容",
    explanation: "导入设置前需要粘贴设置 JSON。",
    suggested_action: "粘贴导出的设置 JSON 后再试运行。",
  },
  "no_llm_items": {
    title: "没有可发送给 LLM 的项目",
    explanation: "当前没有已选项目，也没有需要复核的项目。",
    suggested_action: "先选择项目，或生成包含需复核项的预览。",
  },
  "download_residue_or_shortcut": {
    title: "下载残留或快捷方式",
    explanation: "这是下载器残留文件、种子、临时下载片段或快捷入口，通常不是媒体正片。",
    suggested_action: "可以隔离；如不确定，请先不要勾选执行。",
  },
  "empty_file": {
    title: "空文件",
    explanation: "文件大小为 0，通常是下载残留或占位文件。",
    suggested_action: "可以隔离；如不确定，请先跳过。",
  },
  "advertising_text_or_html_file": {
    title: "广告文本或网页文件",
    explanation: "这是下载包里常见的广告说明、HTML 页面或推广文本。",
    suggested_action: "通常可以隔离。",
  },
  "custom_junk_keyword": {
    title: "命中自定义垃圾关键词",
    explanation: "文件名命中了你在规则设置里配置的垃圾关键词。",
    suggested_action: "确认规则没有误伤后再隔离。",
  },
  "draft": {
    title: "预览草稿",
    explanation: "预览还没有完成当前校验。",
    suggested_action: "执行前先重新校验。",
  },
  "validated": {
    title: "已校验",
    explanation: "计划或批次已经通过当前校验。",
    suggested_action: "继续复核并只执行需要的项目。",
  },
  "stale": {
    title: "已过期",
    explanation: "文件、选择或预览内容发生变化，旧结果不能直接执行。",
    suggested_action: "重新校验或重新生成预览。",
  },
  "executed": {
    title: "已执行",
    explanation: "这个预览已经产生执行批次。",
    suggested_action: "需要恢复时到历史里回滚。",
  },
  "created": {
    title: "已创建",
    explanation: "执行批次已经创建，还没有开始改动。",
    suggested_action: "等待执行流程继续。",
  },
  "running": {
    title: "执行中",
    explanation: "AVcleaner 正在按后端计划处理文件。",
    suggested_action: "等待完成，不要手动移动相关文件。",
  },
  "partial_success": {
    title: "部分成功",
    explanation: "部分项目已完成，部分项目失败或被跳过。",
    suggested_action: "查看批次摘要，再决定是否回滚或重新处理失败项。",
  },
  "success": {
    title: "执行成功",
    explanation: "选中的改名或隔离操作已经完成。",
    suggested_action: "如结果不符合预期，可从历史记录回滚。",
  },
  "failed": {
    title: "失败",
    explanation: "执行或单个项目处理失败，已按安全规则停止相关动作。",
    suggested_action: "查看详情和诊断信息后重试。",
  },
  "rollback_running": {
    title: "回滚中",
    explanation: "AVcleaner 正在尝试恢复本批次已处理的文件。",
    suggested_action: "等待回滚完成。",
  },
  "rolled_back": {
    title: "已回滚",
    explanation: "本批次已恢复到执行前位置。",
    suggested_action: "如需重新处理，请重新扫描并生成预览。",
  },
  "rollback_partial": {
    title: "部分回滚",
    explanation: "部分项目已恢复，部分项目因为冲突或文件变化没有恢复。",
    suggested_action: "检查失败项，尤其是回滚目标已存在的情况。",
  },
  "interrupted": {
    title: "已中断",
    explanation: "执行过程中服务关闭或流程被打断。",
    suggested_action: "查看历史记录，必要时先回滚再重新处理。",
  },
  "cancelled": {
    title: "已取消",
    explanation: "操作已经取消，没有继续执行。",
    suggested_action: "需要处理时重新生成预览。",
  },
  "abandoned": {
    title: "已放弃",
    explanation: "这个批次不再继续执行或回滚。",
    suggested_action: "重新扫描后创建新的预览。",
  },
  "pending": {
    title: "等待处理",
    explanation: "项目还没有开始执行。",
    suggested_action: "等待批次继续。",
  },
  "skipped": {
    title: "已跳过",
    explanation: "项目没有被执行，通常是未选中或不可执行。",
    suggested_action: "需要处理时重新选择并执行。",
  },
  "renamed": {
    title: "已改名",
    explanation: "文件已按计划改名。",
    suggested_action: "如需恢复，请从历史记录回滚。",
  },
  "quarantined": {
    title: "已隔离",
    explanation: "文件已移动到隔离位置，不是永久删除。",
    suggested_action: "如需恢复，请从历史记录回滚。",
  },
  "rollback_failed": {
    title: "回滚失败",
    explanation: "该项目没有恢复成功，通常是目标冲突或文件已变化。",
    suggested_action: "检查回滚目标是否已存在，再手动处理。",
  },
  "valid": {
    title: "建议有效",
    explanation: "LLM 建议通过了结构和安全校验。",
    suggested_action: "仍需人工确认后再接受。",
  },
  "invalid": {
    title: "建议无效",
    explanation: "LLM 建议没有通过校验。",
    suggested_action: "不要接受这条建议。",
  },
  "accepted": {
    title: "已接受",
    explanation: "这条 LLM 建议已写入预览目标名。",
    suggested_action: "执行前仍需重新复核预览。",
  },
  "rejected": {
    title: "已拒绝",
    explanation: "这条 LLM 建议被人工拒绝。",
    suggested_action: "可重新请求建议或手动编辑。",
  },
  "requires_review": {
    title: "需复核",
    explanation: "这一项需要人工确认，AVcleaner 不会替你自动判断。",
    suggested_action: "确认番号、目标名和关联文件后再选择。",
  },
  "warning": {
    title: "警告",
    explanation: "这一项存在需要注意的问题，但不一定会阻止执行。",
    suggested_action: "阅读详情后再决定是否选择。",
  },
  "blocking": {
    title: "阻止",
    explanation: "这一项存在安全阻止问题，不能执行。",
    suggested_action: "修正目标名或跳过这一项。",
  },
  "conflict": {
    title: "冲突",
    explanation: "目标名或回滚目标存在冲突，AVcleaner 不会覆盖文件。",
    suggested_action: "手动修改目标名或处理冲突文件。",
  },
  "selected": {
    title: "已选",
    explanation: "这一项已被加入执行选择。",
    suggested_action: "执行前查看执行摘要。",
  },
  "ok": {
    title: "可处理",
    explanation: "当前没有发现阻止级问题。",
    suggested_action: "仍建议核对目标名后再执行。",
  },
};

const LLM_MODE_COPY = {
  "openai_strict_json_schema": {
    title: "Strict OpenAI JSON Schema",
    body: "适合真正支持 response_format=json_schema 的 OpenAI 兼容供应商。",
  },
  "prompt_json_compat": {
    title: "Prompt JSON compatibility",
    body: "适合自称 OpenAI 兼容但不支持严格 JSON Schema 的网关。",
  },
  "claude_gateway_compat": {
    title: "Claude gateway compatibility",
    body: "适合 Claude/Anthropic 风格的中间层。AVcleaner 会要求 JSON，再提取并严格校验。",
  },
  "ollama_format_json": {
    title: "Ollama",
    body: "适合本地 Ollama JSON mode。",
  },
};

const LLM_SAFETY_COPY = {
  does_not_bypass_validation: "兼容模式不会绕过校验。",
  requires_user_acceptance: "执行前仍需要用户确认。",
  preview_only: "AI 只更新预览目标名，不会执行文件。",
  llm_never_executes_files: "LLM 端点永远不会执行文件。",
};

const LOADING_LABELS = {
  analyze: "分析中",
  scan: "扫描中",
  plan: "生成预览中",
  validate: "校验中",
  llm: "请求 LLM 中",
  execute: "执行中",
  rollback: "回滚中",
  settings: "保存设置中",
  diagnostics: "读取诊断中",
};

function lookupExplanation(code) {
  if (!code) return null;
  return CODE_EXPLANATIONS[code] || SELECTION_LOCK_EXPLANATIONS[code] || null;
}

function severityFor(code) {
  const raw = String(code || "");
  if (["blocking", "target_exists", "target_exists_case_insensitive", "duplicate_target", "duplicate_target_case_insensitive", "path_escape", "extension_changed", "empty_name", "invalid_character", "control_character", "trailing_dot_or_space", "reserved_name", "reserved_name_with_extension", "alternate_data_stream", "source_missing", "source_changed", "path_too_long", "restore_target_exists", "rollback_target_exists", "rollback_source_missing", "quarantine_file_missing", "rollback_file_changed", "unknown_run_item", "rollback_already_completed", "rollback_not_available", "blocking_item_selected", "invalid_target_name", "path_separator_in_target", "plan_hash_mismatch", "legacy_execute_disabled", "legacy_llm_suggest_disabled", "request_extra_fields", "llm_payload_privacy_violation", "blocking_suggestion", "failed", "rollback_failed"].includes(raw)) {
    return "blocking";
  }
  if (raw.startsWith("llm_") || ["warning", "low_confidence", "path_near_limit", "case_only_rename", "download_residue_or_shortcut", "empty_file", "advertising_text_or_html_file", "custom_junk_keyword", "requires_review", "partial_success", "rollback_partial", "interrupted", "abandoned", "invalid"].includes(raw)) {
    return "warning";
  }
  return "info";
}

function explanationFor(code) {
  if (!code) return null;
  const raw = String(code);
  const entry = lookupExplanation(raw);
  if (!entry) {
    return {
      title: "未知状态",
      explanation: "这是未识别的内部稳定码。AVcleaner 会保留 raw code，避免误导判断。",
      suggested_action: "如果影响执行，请复制诊断信息并保留这个 raw code。",
      severity: "info",
      raw_code: raw,
    };
  }
  return {
    ...entry,
    severity: entry.severity || severityFor(raw),
    raw_code: raw,
  };
}

function friendlyCode(code) {
  return explanationFor(code)?.title || STATUS_LABELS[code] || ACTION_LABELS[code] || code || "";
}

function friendlyAction(action) {
  return ACTION_LABELS[String(action || "")] || action || "";
}

function friendlySource(source) {
  return SOURCE_LABELS[String(source || "")] || source || "";
}

function friendlyMessage(message) {
  const raw = String(message || "");
  const [code, extra] = raw.split(":", 2);
  const explanation = lookupExplanation(code);
  if (!explanation) return raw;
  return extra ? `${explanation.title}：${extra}` : explanation.title;
}

function sanitizeFeedbackMessage(message) {
  let text = String(message || "");
  for (const pattern of SECRET_PATTERNS) {
    text = text.replace(pattern, (match) => {
      if (/^[A-Za-z]:\\/.test(match)) return "[路径已隐藏]";
      if (/sk-/.test(match)) return "[已隐藏]";
      const key = match.split(/[:=]/, 1)[0] || "secret";
      return `${key}: [已隐藏]`;
    });
  }
  return text;
}

function showFeedback(message, { type = "info", timeout } = {}) {
  const node = $("#toast");
  if (!node) return;
  const safeType = FEEDBACK_TYPES.has(type) ? type : "info";
  const text = sanitizeFeedbackMessage(friendlyMessage(message));
  node.textContent = text;
  node.className = `toast show ${safeType}`;
  node.setAttribute("role", safeType === "error" || safeType === "warning" ? "alert" : "status");
  if (state.feedbackTimer) window.clearTimeout(state.feedbackTimer);
  const resolvedTimeout = timeout ?? (safeType === "error" ? 9000 : safeType === "loading" ? 0 : 2800);
  if (resolvedTimeout > 0) {
    state.feedbackTimer = window.setTimeout(() => node.classList.remove("show"), resolvedTimeout);
  }
}

function toast(message, type = "info", options = {}) {
  showFeedback(message, { type, ...options });
}

function setStatus(message, type = "info") {
  state.lastStatus = { message: sanitizeFeedbackMessage(friendlyMessage(message)), type };
  const node = $("#lastOperationStatus");
  if (!node) return;
  node.textContent = state.lastStatus.message || "待命";
  node.dataset.status = type;
}

function setText(selector, value) {
  const node = $(selector);
  if (node) node.textContent = value;
}

function setCompactText(selector, value, fallback = "-") {
  const node = $(selector);
  if (!node) return;
  const text = value ? String(value) : fallback;
  node.textContent = shortId(text);
  node.title = text;
}

function shortId(value) {
  const text = String(value || "");
  if (!text || text === "-") return "-";
  return text.length > 14 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

function icon(name, className = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `icon ${className}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/icons.svg#icon-${name}`);
  svg.append(use);
  return svg;
}

function iconButton(iconName, title, extraClass = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `icon-btn ${extraClass}`.trim();
  button.title = title;
  button.setAttribute("aria-label", title);
  button.append(icon(iconName));
  return button;
}

function setButtonContent(button, iconName, label) {
  button.innerHTML = "";
  button.append(icon(iconName), document.createElement("span"));
  button.lastChild.textContent = label;
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      "X-AVCleaner-Token": apiToken,
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error_code || body.detail || "operation_failed");
  }
  return response.json();
}

async function apiText(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "X-AVCleaner-Token": apiToken,
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error_code || body.detail || "operation_failed");
  }
  return response.text();
}

function isBusy(key) {
  return Boolean(state.busy[key]);
}

function busyAny() {
  return Boolean(state.loading) || Object.values(state.busy).some(Boolean);
}

function setBusy(key, value) {
  if (!BUSY_KEYS.includes(key)) return;
  if (value) {
    state.busy[key] = true;
  } else {
    delete state.busy[key];
  }
  document.body.toggleAttribute("aria-busy", busyAny());
  updateSummary();
}

function setLoading(key) {
  state.loading = key || "";
  document.body.toggleAttribute("aria-busy", busyAny());
  document.body.dataset.loading = state.loading || "";
  setText("#loadingState", state.loading ? LOADING_LABELS[state.loading] || "处理中" : "");
  updateSummary();
}

function hasBlocking(item) {
  return Boolean(item?.blocking) || (item?.issues || []).some((issue) => issue.blocking);
}

function hasWarningOnly(item) {
  return (item.issues || []).length > 0 && !hasBlocking(item);
}

function executableAction(item) {
  return ["rename", "quarantine"].includes(String(item?.action || item?.operation || ""));
}

function selectedExecutableItems(plan = state.plan) {
  return (plan?.items || []).filter((item) => item.selected && executableAction(item));
}

function getExecuteButtonState(plan = state.plan) {
  if (!plan) {
    return { enabled: false, reason: "no_plan", selectedCount: 0 };
  }
  if (!plan.plan_hash) {
    return { enabled: false, reason: "plan_hash_missing", selectedCount: 0 };
  }
  if (plan.state === "stale") {
    return { enabled: false, reason: "plan_not_validated", selectedCount: selectedExecutableItems(plan).length };
  }
  const selected = selectedExecutableItems(plan);
  if (!selected.length) {
    return { enabled: false, reason: "no_selected_items", selectedCount: 0 };
  }
  if (selected.some(hasBlocking)) {
    return { enabled: false, reason: "blocking_item_selected", selectedCount: selected.length };
  }
  if (state.executionSummary?.plan_hash && state.executionSummary.plan_hash !== plan.plan_hash) {
    return { enabled: false, reason: "plan_hash_mismatch", selectedCount: selected.length };
  }
  return { enabled: !busyAny(), reason: "", selectedCount: selected.length };
}

function filteredItems() {
  const items = state.plan?.items || [];
  if (state.filter === "selected") return items.filter((item) => item.selected);
  if (state.filter === "safe_selectable") return items.filter((item) => !hasBlocking(item) && !item.requires_review && !item.sidecar_type && executableAction(item));
  if (state.filter === "blocking") return items.filter(hasBlocking);
  if (state.filter === "warning") return items.filter(hasWarningOnly);
  if (state.filter === "requires_review") return items.filter((item) => item.requires_review);
  if (state.filter === "conflict") return items.filter((item) => (item.review_buckets || []).includes("conflict"));
  if (state.filter === "sidecar") return items.filter((item) => item.sidecar_type);
  if (state.filter === "junk_candidate") return items.filter((item) => item.action === "quarantine" || (item.review_buckets || []).includes("junk_candidate"));
  if (state.filter === "manual_edited") return items.filter((item) => item.manual_edited);
  return items;
}

function filterCounts() {
  const items = state.plan?.items || [];
  return {
    all: items.length,
    selected: items.filter((item) => item.selected).length,
    safe_selectable: items.filter((item) => !hasBlocking(item) && !item.requires_review && !item.sidecar_type && executableAction(item)).length,
    blocking: items.filter(hasBlocking).length,
    warning: items.filter(hasWarningOnly).length,
    requires_review: items.filter((item) => item.requires_review).length,
    conflict: items.filter((item) => (item.review_buckets || []).includes("conflict")).length,
    sidecar: items.filter((item) => item.sidecar_type).length,
    junk_candidate: items.filter((item) => item.action === "quarantine" || (item.review_buckets || []).includes("junk_candidate")).length,
    manual_edited: items.filter((item) => item.manual_edited).length,
  };
}

function renderFilterOptions() {
  const filter = $("#filterSelect");
  if (!filter) return;
  const previous = state.filter;
  const counts = filterCounts();
  const options = [
    ["all", "全部"],
    ["selected", "已选"],
    ["safe_selectable", "可安全选择"],
    ["blocking", "阻止"],
    ["warning", "警告"],
    ["requires_review", "需复核"],
    ["conflict", "冲突"],
    ["sidecar", "关联文件"],
    ["junk_candidate", "垃圾候选"],
    ["manual_edited", "手动修改"],
  ];
  filter.innerHTML = "";
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${label} (${counts[value] || 0})`;
    filter.append(option);
  }
  filter.value = options.some(([value]) => value === previous) ? previous : "all";
}

function updateSummary() {
  const items = state.plan?.items || [];
  const summary = state.plan?.summary || {};
  const blocking = summary.blocking_items ?? items.filter(hasBlocking).length;
  const selected = selectedExecutableItems().length;
  setText("#metricFiles", state.scan?.total_files || 0);
  setText("#metricRename", summary.rename_items ?? items.filter((item) => item.action === "rename").length);
  setText("#metricQuarantine", summary.quarantine_items ?? items.filter((item) => item.action === "quarantine").length);
  setText("#metricSidecar", summary.sidecar_items ?? items.filter((item) => item.sidecar_type).length);
  setText("#metricSelected", summary.selected_items ?? items.filter((item) => item.selected).length);
  setText("#metricBlocking", blocking);
  setText("#metricWarning", summary.warning_items ?? items.filter(hasWarningOnly).length);
  setText("#metricReview", summary.requires_review_items ?? items.filter((item) => item.requires_review).length);
  setText("#metricManual", summary.manual_edited_items ?? items.filter((item) => item.manual_edited).length);
  setCompactText("#scanId", state.scan?.scan_id || "-");
  setCompactText("#planId", state.plan?.plan_id || "-");
  setText("#planState", state.plan?.state ? friendlyCode(String(state.plan.state)) : "-");
  setCompactText("#planHash", state.plan?.plan_hash || "-");
  setText("#blockingCount", blocking);
  setText("#statusSelectedCount", selected);
  setText("#selectedCount", selected);
  setText("#currentMode", state.diagnostics?.summary?.runtime_mode || state.diagnostics?.runtime?.mode || "-");
  setStatus(state.lastStatus.message || "待命", state.lastStatus.type || "info");

  const executeState = getExecuteButtonState();
  const executeBtn = $("#executeBtn");
  if (executeBtn) {
    executeBtn.disabled = !executeState.enabled;
    executeBtn.title = executeState.reason ? `${friendlyCode(executeState.reason)} | code: ${executeState.reason}` : "执行前会再次显示摘要并要求确认";
  }
  setText("#executeReason", executeState.reason ? explanationFor(executeState.reason)?.suggested_action || friendlyCode(executeState.reason) : "会先显示执行摘要，并再次要求确认。");

  const isBusyNow = busyAny();
  for (const id of ["#validateBtn", "#selectSafeBtn", "#clearSelectionBtn", "#exportPlanJsonBtn", "#exportPlanCsvBtn", "#executionSummaryBtn", "#previewLlmPayloadBtn", "#llmBtn"]) {
    const node = $(id);
    if (!node) continue;
    node.disabled = isBusyNow || !state.plan;
  }
  const scanBtn = $("#scanBtn");
  if (scanBtn) scanBtn.disabled = isBusyNow;
  const planBtn = $("#planBtn");
  if (planBtn) planBtn.disabled = isBusyNow || !state.scan;
  const analyzeBtn = $("#analyzeBtn");
  if (analyzeBtn) {
    analyzeBtn.disabled = isBusyNow;
    analyzeBtn.classList.toggle("is-busy", isBusy("analyzing") || isBusy("requestingAi"));
  }
  const folderPickerBtn = $("#folderPickerBtn");
  if (folderPickerBtn) folderPickerBtn.disabled = isBusyNow;
  const llmSection = $("#llmSection");
  if (llmSection) llmSection.hidden = true;
  renderFilterOptions();
}

function cell(node, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.append(node);
  return td;
}

function cellText(text, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  td.textContent = text || "";
  return td;
}

function truncateText(text, className = "truncate") {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text || "-";
  span.title = text || "-";
  return span;
}

function badge(label, code = "", variant = "") {
  const span = document.createElement("span");
  span.className = `badge ${variant}`.trim();
  span.textContent = label;
  if (code) {
    span.dataset.code = code;
    span.title = `${label} | code: ${code}`;
  }
  return span;
}

function actionPill(item) {
  const action = String(item.action || item.operation || "");
  const span = badge(friendlyAction(action), action, `action-${action}`);
  if (hasBlocking(item)) span.classList.add("is-blocking");
  return span;
}

function statusBadges(item) {
  const wrap = document.createElement("div");
  wrap.className = "badge-row";
  wrap.append(actionPill(item));
  if (hasBlocking(item)) wrap.append(badge("阻止", "blocking", "danger"));
  if (item.warning_count) wrap.append(badge("警告", "warning", "warn"));
  if (item.requires_review) wrap.append(badge("需复核", "requires_review", "warn"));
  if ((item.review_buckets || []).includes("conflict")) wrap.append(badge("冲突", "conflict", "danger"));
  if (item.sidecar_type) wrap.append(badge(sidecarLabel(item), sidecarReasonCode(item), "muted"));
  if (item.manual_edited) wrap.append(badge("手动修改", "manual_edited", "info"));
  return wrap;
}

function renderIssueSummary(item) {
  const wrap = document.createElement("div");
  wrap.className = "badge-row compact-badges review-summary two-line";
  const codes = issueCodes(item);
  if (!codes.length) {
    wrap.append(badge("可处理", "ok", "info"));
    return wrap;
  }
  for (const code of codes.slice(0, 3)) {
    const explanation = explanationFor(code);
    wrap.append(badge(explanation?.title || friendlyCode(code), code, explanation?.severity === "blocking" ? "danger" : explanation?.severity === "warning" ? "warn" : "info"));
  }
  if (codes.length > 3) wrap.append(badge(`+${codes.length - 3}`, "more_codes", "muted"));
  return wrap;
}

function sidecarReasonCode(item) {
  if (!item.sidecar_type) return "";
  if (item.sidecar_type === "image" && item.selected_default === false) return "image_default_off";
  if (item.sidecar_type === "nfo" && item.selected_default === false) return "nfo_default_off";
  if (item.sidecar_type === "subtitle") return "subtitle_sidecar";
  return "sidecar_default_off";
}

function sidecarLabel(item) {
  if (!item.sidecar_type) return "";
  const labels = {
    subtitle: "字幕",
    image: "图片",
    nfo: "NFO",
    other: "关联",
  };
  const parts = [labels[item.sidecar_type] || item.sidecar_type];
  if (item.language_suffix) parts.push(item.language_suffix);
  if (item.selected_default === false) parts.push("默认关闭");
  return parts.join(" ");
}

function issueCodes(item) {
  return [...new Set([
    ...(item.review_reason_codes || []),
    ...(item.warnings || []),
    ...(item.issues || []).map((issue) => (typeof issue === "string" ? issue : issue.code)),
  ].filter(Boolean))];
}

function reasonSummary(item) {
  const code = item.reason || (item.requires_review ? "requires_review" : "");
  const explanation = explanationFor(code);
  const wrap = document.createElement("div");
  wrap.className = "reason-cell";
  const title = document.createElement("div");
  title.className = "cell-title";
  title.textContent = explanation?.title || friendlyCode(code);
  if (code) title.title = `code: ${code}`;
  const body = document.createElement("div");
  body.className = "muted";
  body.textContent = explanation?.suggested_action || "";
  wrap.append(title, body);
  return wrap;
}

function renderIssueList(item) {
  const list = document.createElement("div");
  list.className = "detail-list";
  const issues = item.issues || [];
  const codes = issueCodes(item);
  if (!issues.length && !codes.length) {
    list.append(detailLine("状态", "没有阻止或警告。"));
    return list;
  }
  for (const code of codes) {
    const explanation = explanationFor(code);
    list.append(detailLine(explanation?.title || friendlyCode(code), explanation?.explanation || code, code));
  }
  for (const issue of issues) {
    if (!issue.details || !Object.keys(issue.details).length) continue;
    list.append(detailLine("校验细节", JSON.stringify(issue.details), issue.code));
  }
  return list;
}

function renderTraceList(item) {
  const list = document.createElement("div");
  list.className = "trace-list";
  if (!(item.trace || []).length) {
    list.append(detailLine("Trace", "没有可显示的规则 trace。"));
    return list;
  }
  for (const step of item.trace || []) {
    const node = document.createElement("div");
    node.className = "trace-step";
    node.textContent = [
      step.rule_id,
      `前=${step.before || ""}`,
      `后=${step.after || ""}`,
      `移除=${(step.removed_tokens || []).join(",") || "-"}`,
      `保留=${(step.preserved_tokens || []).join(",") || "-"}`,
      `警告=${(step.warnings || []).map(friendlyCode).join(",") || "-"}`,
    ].join(" | ");
    node.title = `code: ${step.rule_id}`;
    list.append(node);
  }
  return list;
}

function renderSidecarDetails(item) {
  const list = document.createElement("div");
  list.className = "detail-list";
  if (!item.sidecar_type) {
    list.append(detailLine("关联文件", "不是关联文件。"));
    return list;
  }
  list.append(detailLine("类型", sidecarLabel(item), sidecarReasonCode(item)));
  list.append(detailLine("关联番号", item.associated_media_code || item.media_code || "-"));
  list.append(detailLine("分组", groupLabel(item) || "-"));
  list.append(detailLine("默认选择", item.selected_default === false ? "默认不选中" : "默认选中"));
  return list;
}

function detailLine(title, text, code = "") {
  const node = document.createElement("div");
  node.className = "detail-line";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const span = document.createElement("span");
  span.textContent = text || "";
  if (code) span.title = `code: ${code}`;
  node.append(strong, span);
  return node;
}

function detailSection(title, content) {
  const section = document.createElement("section");
  section.className = "detail-section";
  const heading = document.createElement("h4");
  heading.textContent = title;
  section.append(heading, content);
  return section;
}

function groupLabel(item) {
  return item.group_id ? `${item.associated_media_code || item.media_code || "group"}:${item.group_id.slice(-6)}` : "";
}

function latestSuggestionFor(item) {
  return (state.llmSuggestions || []).find((suggestion) => suggestion.item_id === item.id && !["rejected", "stale"].includes(suggestion.status));
}

function previewSource(item) {
  if (item.manual_edited || item.source === "manual" || item.suggestion_source === "manual") return "manual";
  if (item.llm_state === "applied_to_preview" || item.source === "llm" || item.suggestion_source === "llm") return "llm";
  if (["invalid", "schema_error", "safety_error", "provider_error", "not_configured"].includes(item.llm_state)) return "rule_fallback";
  return "rule";
}

function openDetailDrawer(itemId) {
  state.detailItemId = itemId || "";
  renderPlan();
}

function closeDetailDrawer() {
  state.detailItemId = "";
  renderDetailDrawer();
  for (const row of document.querySelectorAll("#planBody tr")) {
    row.classList.remove("selected-row");
    row.setAttribute("aria-selected", "false");
  }
}

function renderDetailDrawer() {
  const panel = $("#detailDrawerPanel");
  const body = $("#detailDrawerBody");
  if (!panel || !body) return;
  const item = (state.plan?.items || []).find((candidate) => candidate.id === state.detailItemId);
  body.innerHTML = "";
  if (!item) {
    setText("#detailDrawerTitle", "未选择项目");
    body.append(emptyStateNode("未选择项目", "点击左侧表格中的一行查看完整路径、问题代码、Trace、AI 细节和 Debug 信息。", "details"));
    return;
  }
  setText("#detailDrawerTitle", item.original_name || item.id);
  const fileDetails = document.createElement("div");
  fileDetails.className = "detail-list";
  fileDetails.append(
    detailLine("item_id", item.id || "-"),
    detailLine("原文件", item.original_name || "-"),
    detailLine("相对路径", item.relative_path || item.source_rel_path || item.original_name || "-"),
    detailLine("最终文件名", item.target_name || item.suggested_name || "-"),
    detailLine("操作类型", friendlyAction(item.action || item.operation)),
    detailLine("来源", SOURCE_LABELS[previewSource(item)] || friendlySource(item.source || item.suggestion_source) || "-"),
    detailLine("识别番号", item.media_code || item.associated_media_code || "-"),
    detailLine("置信度", Number(item.confidence || 0).toFixed(2))
  );

  const codeDetails = document.createElement("div");
  codeDetails.className = "detail-list";
  codeDetails.append(detailLine("问题代码", issueCodes(item).join("；") || "-", "issue_codes"));
  const suggestion = explanationFor(item.reason || issueCodes(item)[0]);
  codeDetails.append(detailLine("建议动作", suggestion?.suggested_action || "-", item.reason || issueCodes(item)[0] || ""));

  const llmDetails = document.createElement("div");
  llmDetails.className = "detail-list";
  llmDetails.append(
    detailLine("AI 状态", LLM_STATE_LABELS[item.llm_state] || item.llm_state || "-"),
    detailLine("AI 建议", item.llm_suggested_name || "-"),
    detailLine("AI 原因", item.llm_reason || "-"),
    detailLine("AI 稳定码", [...new Set([...(item.llm_validation_codes || []), item.llm_error_code].filter(Boolean))].join("；") || "-")
  );

  const debugDetails = document.createElement("details");
  debugDetails.className = "raw-json";
  const summary = document.createElement("summary");
  summary.textContent = "Debug JSON";
  const pre = document.createElement("pre");
  pre.className = "test-result";
  pre.textContent = JSON.stringify(item, null, 2);
  debugDetails.append(summary, pre);

  body.append(
    detailSection("文件", fileDetails),
    detailSection("复核信息", renderIssueList(item)),
    detailSection("问题代码", codeDetails),
    detailSection("AI 细节", llmDetails),
    detailSection("关联文件", renderSidecarDetails(item)),
    detailSection("Trace", renderTraceList(item)),
    detailSection("原始详情", debugDetails)
  );
}

async function saveManualEdit(item, nameInput, previousValue) {
  if (!state.plan?.plan_id) return;
  if (nameInput.value === previousValue) return;
  state.executionSummary = null;
  state.rowSaving[item.id] = true;
  setBusy("savingEdit", true);
  nameInput.classList.add("is-saving");
  nameInput.disabled = true;
  try {
    const response = await api(`/api/plans/${state.plan.plan_id}/items/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ target_name: nameInput.value }),
    });
    state.plan.plan_hash = response.plan_hash;
    state.plan.summary = response.summary;
    for (const affected of response.affected_items) {
      const index = state.plan.items.findIndex((rowItem) => rowItem.id === affected.id);
      if (index >= 0) state.plan.items[index] = affected;
    }
    const editedIndex = state.plan.items.findIndex((rowItem) => rowItem.id === response.item.id);
    if (editedIndex >= 0) state.plan.items[editedIndex] = response.item;
    toast("手动修改已保存", "success");
    setStatus("手动修改已保存", "success");
  } catch (error) {
    nameInput.value = previousValue;
    toast(`手动修改失败：${error.message}`, "error");
    setStatus("手动修改失败", "error");
  } finally {
    delete state.rowSaving[item.id];
    setBusy("savingEdit", false);
    renderPlan();
  }
}

function emptyStateNode(title, body = "", iconName = "empty") {
  const wrap = document.createElement("div");
  wrap.className = "empty-state";
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("class", "icon");
  icon.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `/static/icons.svg#icon-${iconName}`);
  icon.append(use);
  const heading = document.createElement("strong");
  heading.textContent = title;
  const text = document.createElement("span");
  text.textContent = body;
  wrap.append(icon, heading, text);
  return wrap;
}

function emptyRow(title, body = "") {
  const row = document.createElement("tr");
  row.className = "empty-row";
  const td = document.createElement("td");
  td.colSpan = PLAN_TABLE_COLS;
  const wrap = emptyStateNode(title, body);
  td.append(wrap);
  row.append(td);
  return row;
}

function renderPlan() {
  const body = $("#planBody");
  if (!body) return;
  body.innerHTML = "";
  if (state.loading === "scan" || state.loading === "analyze") {
    body.append(emptyRow("分析中", "正在扫描并生成安全预览，不会改动文件。"));
  } else if (state.loading === "plan" || state.loading === "llm") {
    body.append(emptyRow("生成预览中", "正在创建安全预览，不会改动文件。"));
  } else if (!state.scan) {
    body.append(emptyRow("未分析", "先选择文件夹和预览模式，再点击分析。"));
  } else if (!state.plan) {
    body.append(emptyRow("未生成预览", "点击规则预览或 AI 智能预览后再复核。"));
  } else {
    const visible = filteredItems();
    if (!visible.length) {
      body.append(emptyRow("没有符合当前筛选的项目", "切换筛选条件或清空选择后再看。"));
    }
    for (const item of visible) {
      const row = document.createElement("tr");
      row.dataset.id = item.id;
      row.className = state.detailItemId === item.id ? "selected-row" : "";
      row.tabIndex = 0;
      row.setAttribute("aria-selected", state.detailItemId === item.id ? "true" : "false");
      row.addEventListener("click", (event) => {
        if (event.target.closest("input, button, select, textarea, label, a")) return;
        openDetailDrawer(item.id);
      });
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          openDetailDrawer(item.id);
        }
      });

      const checked = document.createElement("input");
      checked.type = "checkbox";
      checked.checked = item.selected;
      checked.disabled = !executableAction(item) || hasBlocking(item) || item.selection_locked || busyAny();
      const lockReason = item.selection_reason || (hasBlocking(item) ? "blocking" : "");
      if (checked.disabled && lockReason) checked.title = `${friendlyCode(lockReason)} | code: ${lockReason}`;
      checked.addEventListener("click", (event) => event.stopPropagation());
      checked.addEventListener("change", () => {
        state.executionSummary = null;
        updateSelection(checked.checked ? "add" : "remove", [item.id]).catch((error) => {
          toast(error.message, "error");
          renderPlan();
        });
      });

      const nameInput = document.createElement("input");
      nameInput.className = "name-input";
      nameInput.value = item.target_name || item.suggested_name;
      nameInput.disabled = item.action === "quarantine" || item.action === "keep" || busyAny() || Boolean(state.rowSaving[item.id]);
      if (state.rowSaving[item.id]) nameInput.classList.add("is-saving");
      const previousValue = nameInput.value;
      nameInput.addEventListener("click", (event) => event.stopPropagation());
      nameInput.addEventListener("change", () => saveManualEdit(item, nameInput, previousValue));
      nameInput.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Enter") {
          event.preventDefault();
          nameInput.blur();
        }
      });

      const detailButton = iconButton("details", state.detailItemId === item.id ? "关闭详情" : "查看详情");
      detailButton.disabled = busyAny();
      detailButton.addEventListener("click", (event) => {
        event.stopPropagation();
        if (state.detailItemId === item.id) {
          closeDetailDrawer();
        } else {
          openDetailDrawer(item.id);
        }
      });

      const original = document.createElement("div");
      original.className = "file-cell";
      original.append(truncateText(item.original_name, "file-name truncate"));
      original.title = item.relative_path || item.source_rel_path || item.original_name || "";

      const targetWrap = document.createElement("div");
      targetWrap.className = "target-editor";
      targetWrap.append(nameInput);
      if (state.rowSaving[item.id]) {
        const saving = document.createElement("span");
        saving.className = "saving-dot";
        saving.textContent = "保存中";
        targetWrap.append(saving);
      }

      row.append(
        cell(checked, "check-col"),
        cell(statusBadges(item), "status-col"),
        cell(original, "name-col"),
        cell(targetWrap, "target-col"),
        cell(badge(SOURCE_LABELS[previewSource(item)] || previewSource(item), previewSource(item), previewSource(item) === "rule_fallback" ? "warn" : "info"), "source-col"),
        cell(renderIssueSummary(item), "badge-col"),
        cell(detailButton, "detail-col")
      );
      body.append(row);
    }
  }
  renderDetailDrawer();
  renderTrash();
  updateSummary();
}

function renderTrash() {
  const body = $("#trashBody");
  if (!body) return;
  body.innerHTML = "";
  const items = (state.plan?.items || []).filter((row) => row.action === "quarantine");
  if (!items.length) {
    const row = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.append(document.createTextNode(state.plan ? "当前预览没有隔离候选。" : "未生成预览。"));
    row.append(td);
    body.append(row);
    return;
  }
  for (const item of items) {
    const row = document.createElement("tr");
    row.append(
      cellText(item.original_name),
      cellText(item.relative_path),
      cell(quarantineReasonNode(item)),
      cellText(item.selected ? "已选中" : "未选中"),
      cellText(formatSize(item.size))
    );
    body.append(row);
  }
}

function isLargeThunderTempFile(item) {
  const name = String(item?.original_name || item?.relative_path || "").toLowerCase();
  return (name.endsWith(".xltd") || name.endsWith(".bt.xltd")) && Number(item?.size || 0) >= 100 * 1024 * 1024;
}

function quarantineReasonNode(item) {
  const explanation = explanationFor(item.reason || "download_residue_or_shortcut");
  const wrap = document.createElement("div");
  wrap.className = "reason-cell quarantine-reason";
  wrap.title = `${explanation.title} | code: ${explanation.raw_code}`;

  const title = document.createElement("div");
  title.className = "cell-title";
  title.textContent = explanation.title;

  const body = document.createElement("div");
  body.className = "muted";
  body.textContent = explanation.explanation;

  const action = document.createElement("div");
  action.className = "muted";
  action.textContent = explanation.suggested_action;

  wrap.append(title, body, action);
  if (isLargeThunderTempFile(item)) {
    const warning = document.createElement("div");
    warning.className = "inline-error quarantine-warning";
    warning.textContent = "大文件隔离可能耗时，但仍不会永久删除。";
    wrap.append(warning);
  }
  return wrap;
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function linesFromTextarea(selector) {
  return ($(selector)?.value || "")
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function setTextareaLines(selector, values) {
  const node = $(selector);
  if (node) node.value = (values || []).join("\n");
}

function syncRuleFormFromSettings() {
  const rules = state.settings.rules || {};
  const quarantineInput = $("#quarantineDir");
  if (quarantineInput) quarantineInput.value = state.settings.quarantine_dir || "";
  $("#ruleOutputTemplate").value = rules.output_template || "{code}{part}{variant}{language}{ext}";
  setTextareaLines("#ruleRemoveAdDomains", rules.remove_ad_domains || []);
  setTextareaLines("#ruleRemoveNoiseTokens", rules.remove_noise_tokens || []);
  $("#rulePreserveSidecarLanguage").checked = rules.preserve_sidecar_language !== false;
  $("#rulePreserveVariant").checked = rules.preserve_variant !== false;
  $("#rulePreservePartSuffix").checked = rules.preserve_part_suffix !== false;
  $("#ruleReviewThreshold").value = rules.review_threshold ?? 0.7;
}

function syncRuleFormToSettings() {
  state.settings.rules = state.settings.rules || {};
  const quarantineInput = $("#quarantineDir");
  state.settings.quarantine_dir = quarantineInput ? quarantineInput.value.trim() : "";
  state.settings.rules.output_template = $("#ruleOutputTemplate").value.trim() || "{code}{part}{variant}{language}{ext}";
  state.settings.rules.remove_ad_domains = linesFromTextarea("#ruleRemoveAdDomains");
  state.settings.rules.remove_noise_tokens = linesFromTextarea("#ruleRemoveNoiseTokens");
  state.settings.rules.preserve_sidecar_language = $("#rulePreserveSidecarLanguage").checked;
  state.settings.rules.preserve_variant = $("#rulePreserveVariant").checked;
  state.settings.rules.preserve_part_suffix = $("#rulePreservePartSuffix").checked;
  state.settings.rules.review_threshold = Number($("#ruleReviewThreshold").value || 0.7);
}

function updateLlmModeHelp() {
  const mode = $("#llmCompatibilityMode")?.value || "openai_strict_json_schema";
  const help = $("#llmModeHelp");
  if (!help) return;
  const copy = LLM_MODE_COPY[mode];
  const safety = Object.entries(LLM_SAFETY_COPY).map(([code, text]) => `<li title="code: ${code}">${text}</li>`).join("");
  help.innerHTML = `<strong>${copy.title}</strong><p>${copy.body}</p><ul>${safety}</ul>`;
}

function renderFirstRunHelper() {
  const helper = $("#firstRunHelper");
  if (!helper) return;
  helper.hidden = Boolean(state.settings?.first_run_seen || state.scan || state.plan);
}

function boolLabel(value) {
  return value ? "是" : "否";
}

function statusLabel(value) {
  return value ? "正常" : "异常";
}

function summaryItem(label, value, code = "") {
  const node = document.createElement("div");
  node.className = "summary-item";
  const strong = document.createElement("strong");
  strong.textContent = label;
  const span = document.createElement("span");
  span.textContent = value ?? "-";
  if (code) span.title = `code: ${code}`;
  node.append(strong, span);
  return node;
}

function renderDiagnosticsSummary(payload) {
  const target = $("#diagnosticsSummary");
  if (!target) return;
  const summary = payload?.summary || {};
  target.innerHTML = "";
  target.append(
    summaryItem("版本", summary.version || payload?.app?.version || "-"),
    summaryItem("运行模式", summary.runtime_mode || payload?.runtime?.mode || "-"),
    summaryItem("数据目录可写", statusLabel(Boolean(summary.data_dir_writable))),
    summaryItem("数据库状态", statusLabel(Boolean(summary.database_ok))),
    summaryItem("模板资源", statusLabel(Boolean(summary.templates_ok))),
    summaryItem("静态资源", statusLabel(Boolean(summary.static_ok))),
    summaryItem("keyring 状态", statusLabel(Boolean(summary.keyring_ok))),
    summaryItem("旧执行接口", summary.legacy_execute_disabled ? "已禁用" : "异常", "legacy_execute_disabled"),
    summaryItem("通用 LLM 接口", summary.generic_llm_suggest_disabled ? "已禁用" : "异常", "legacy_llm_suggest_disabled"),
    summaryItem("LLM 已配置", boolLabel(Boolean(summary.llm_configured))),
    summaryItem("默认发送完整路径", boolLabel(Boolean(summary.send_full_path_default)))
  );
}

function renderLlmTestSummary(response) {
  const target = $("#llmTestSummary");
  if (!target) return;
  target.innerHTML = "";
  const error = response?.error_code ? explanationFor(response.error_code) : null;
  target.append(
    summaryItem("测试结果", response?.ok ? "测试成功" : "测试失败", response?.error_code || ""),
    summaryItem("Provider", response?.provider || "-"),
    summaryItem("Model", response?.model || "-"),
    summaryItem("Compatibility mode", response?.compatibility_mode || "-"),
    summaryItem("使用 strict schema", boolLabel(Boolean(response?.used_response_format_json_schema))),
    summaryItem("从 Markdown/文本提取 JSON", boolLabel(Boolean(response?.json_extracted))),
    summaryItem("Schema 校验", response?.schema_valid === null || response?.schema_valid === undefined ? "-" : statusLabel(Boolean(response.schema_valid))),
    summaryItem("安全校验", response?.safety_valid === null || response?.safety_valid === undefined ? "-" : statusLabel(Boolean(response.safety_valid))),
    summaryItem("错误码", response?.error_code ? `${response.error_code}：${error?.title || "未知状态"}` : "-")
  );
}

function llmConfigured() {
  const llm = state.settings?.llm || {};
  return llm.provider && llm.provider !== "disabled" && Boolean(llm.model);
}

function aiPreviewAvailable() {
  const caps = state.capabilities?.capabilities || {};
  return Boolean(caps.ai_smart_preview || caps.ai_preview || llmConfigured());
}

function renderPreviewModeControls() {
  const aiButton = document.querySelector('[data-preview-mode="ai"]');
  if (aiButton) aiButton.hidden = !aiPreviewAvailable();
  if (state.previewMode === "ai" && !aiPreviewAvailable()) state.previewMode = "rule";
  for (const button of document.querySelectorAll("[data-preview-mode]")) {
    const active = button.dataset.previewMode === state.previewMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
  const analyzeBtn = $("#analyzeBtn");
  if (analyzeBtn) {
    setButtonContent(analyzeBtn, state.previewMode === "ai" && aiPreviewAvailable() ? "ai" : "analyze", state.previewMode === "ai" && aiPreviewAvailable() ? "AI 智能预览" : "规则预览");
    analyzeBtn.title = state.previewMode === "ai" && aiPreviewAvailable() ? "扫描并生成 AI 智能预览，不会执行文件" : "扫描并生成规则预览，不会执行文件";
  }
}

async function loadCapabilities() {
  state.capabilities = await api("/api/capabilities");
  renderPreviewModeControls();
}

async function dismissFirstRunHelper() {
  if (!state.settings) return;
  state.settings.first_run_seen = true;
  state.settings = await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify(state.settings),
  });
  renderFirstRunHelper();
  toast("已关闭新手提示", "success");
}

async function loadSettings() {
  state.settings = await api("/api/settings");
  $("#llmProvider").value = state.settings.llm.provider;
  $("#llmCompatibilityMode").value = state.settings.llm.compatibility_mode || "openai_strict_json_schema";
  $("#llmBaseUrl").value = state.settings.llm.base_url;
  $("#llmModel").value = state.settings.llm.model;
  $("#llmApiKey").value = state.settings.llm.api_key || "";
  $("#llmSendPath").checked = state.settings.llm.send_full_path;
  syncRuleFormFromSettings();
  updateLlmModeHelp();
  renderFirstRunHelper();
  renderPreviewModeControls();
}

async function persistSettingsFromForm({ showSuccess = true } = {}) {
  syncRuleFormToSettings();
  state.settings.llm.provider = $("#llmProvider").value;
  state.settings.llm.compatibility_mode = $("#llmCompatibilityMode").value;
  state.settings.llm.base_url = $("#llmBaseUrl").value;
  state.settings.llm.model = $("#llmModel").value;
  state.settings.llm.api_key = $("#llmApiKey").value;
  state.settings.llm.send_full_path = $("#llmSendPath").checked;
  state.settings = await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify(state.settings),
  });
  $("#llmApiKey").value = "";
  renderFirstRunHelper();
  renderPreviewModeControls();
  if (showSuccess) {
    toast("设置已保存", "success");
    setStatus("设置已保存", "success");
  }
  return state.settings;
}

async function saveSettings() {
  if (isBusy("validating")) return;
  setBusy("validating", true);
  setLoading("settings");
  showFeedback("保存设置中", { type: "loading" });
  setStatus("保存设置中", "loading");
  try {
    await persistSettingsFromForm();
  } finally {
    setBusy("validating", false);
    setLoading("");
  }
}
async function testLlm() {
  if (isBusy("requestingAi") || isBusy("validating")) return;
  setBusy("validating", true);
  setLoading("settings");
  showFeedback("保存 LLM 设置中", { type: "loading" });
  setStatus("保存 LLM 设置中", "loading");
  try {
    await persistSettingsFromForm({ showSuccess: false });
    setBusy("validating", false);
    setBusy("requestingAi", true);
    setLoading("llm");
    showFeedback("LLM 测试中", { type: "loading" });
    setStatus("LLM 测试中", "loading");
    const response = await api("/api/llm/test", {
      method: "POST",
      body: JSON.stringify({}),
    });
    renderLlmTestSummary(response);
    $("#llmTestResult").textContent = JSON.stringify(response, null, 2);
    toast(response.ok ? "LLM 测试完成" : "LLM 测试失败", response.ok ? "success" : "warning");
    setStatus(response.ok ? "LLM 测试完成" : "LLM 测试失败", response.ok ? "success" : "warning");
  } finally {
    setBusy("validating", false);
    setBusy("requestingAi", false);
    setLoading("");
  }
}
async function testRules() {
  const filename = $("#ruleTestFilename").value.trim();
  if (!filename) {
    toast("filename_required");
    return;
  }
  const response = await api("/api/rules/test", {
    method: "POST",
    body: JSON.stringify({
      filename,
      settings_override: {
        output_template: $("#ruleOutputTemplate").value.trim() || "{code}{part}{variant}{language}{ext}",
        remove_ad_domains: linesFromTextarea("#ruleRemoveAdDomains"),
        remove_noise_tokens: linesFromTextarea("#ruleRemoveNoiseTokens"),
        preserve_sidecar_language: $("#rulePreserveSidecarLanguage").checked,
        preserve_variant: $("#rulePreserveVariant").checked,
        preserve_part_suffix: $("#rulePreservePartSuffix").checked,
        review_threshold: Number($("#ruleReviewThreshold").value || 0.7),
      },
    }),
  });
  $("#ruleTestResult").textContent = JSON.stringify(response, null, 2);
}

async function exportSettings() {
  const response = await api("/api/settings/export");
  const text = JSON.stringify(response, null, 2);
  $("#settingsExportResult").textContent = text;
  $("#settingsImportPayload").value = JSON.stringify(response.settings, null, 2);
}

async function importSettings(dryRun) {
  const raw = $("#settingsImportPayload").value.trim();
  if (!raw) {
    toast("settings_import_required");
    return;
  }
  const response = await api("/api/settings/import", {
    method: "POST",
    body: JSON.stringify({ settings: JSON.parse(raw), dry_run: dryRun }),
  });
  $("#settingsImportResult").textContent = JSON.stringify(response, null, 2);
  if (!dryRun && response.settings) {
    await loadSettings();
  }
}

function renderRecentFolders() {
  const target = $("#recentFolders");
  if (!target) return;
  target.innerHTML = "";
  if (!state.recentFolders.length) {
    const span = document.createElement("span");
    span.className = "muted";
    span.textContent = "暂无最近记录";
    target.append(span);
    return;
  }
  for (const folder of state.recentFolders) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "recent-folder";
    button.textContent = `${folder.display_name || folder.path} (${folder.item_count || 0})`;
    button.title = folder.path;
    button.addEventListener("click", () => {
      $("#rootPath").value = folder.path;
      toast("已填入最近文件夹，请点击预览按钮");
    });
    target.append(button);
  }
}

async function loadRecentFolders() {
  state.recentFolders = await api("/api/recent-folders");
  renderRecentFolders();
}

async function loadFolderPickerState() {
  state.folderPickerState = await api("/api/folder-picker-state");
}

async function saveFolderPickerState(path) {
  state.folderPickerState = await api("/api/folder-picker-state", {
    method: "PUT",
    body: JSON.stringify({ last_folder_dialog_dir: path || "" }),
  });
}

function folderPickerInitialDir() {
  return $("#rootPath")?.value.trim()
    || state.folderPickerState?.last_folder_dialog_dir
    || state.recentFolders?.[0]?.path
    || "";
}

async function chooseFolder() {
  const bridge = window.pywebview?.api;
  if (!bridge?.choose_folder) {
    toast("浏览器模式不支持系统文件夹选择窗口，请手动粘贴路径。", "warning");
    setStatus("浏览器模式不支持系统文件夹选择窗口", "warning");
    return;
  }
  showFeedback("正在打开文件夹选择窗口", { type: "loading" });
  const response = await bridge.choose_folder(folderPickerInitialDir());
  if (!response?.ok || !response.path) {
    toast("已取消选择文件夹", "info");
    setStatus("已取消选择文件夹", "info");
    return;
  }
  $("#rootPath").value = response.path;
  await saveFolderPickerState(response.path).catch(() => {});
  toast("已选择文件夹", "success");
  setStatus("已选择文件夹", "success");
}

async function clearRecentFolders() {
  await api("/api/recent-folders", { method: "DELETE" });
  state.recentFolders = [];
  renderRecentFolders();
  toast("最近记录已清除", "success");
  setStatus("最近记录已清除", "success");
}

async function analyze() {
  const root = $("#rootPath").value.trim();
  if (!root) {
    toast("root_required", "warning");
    setStatus("root_required", "warning");
    return;
  }
  const mode = state.previewMode === "ai" && aiPreviewAvailable() ? "ai" : "rule";
  if (isBusy("analyzing") || isBusy("requestingAi")) return;
  const previousScan = state.scan;
  const previousPlan = state.plan;
  state.scan = null;
  state.plan = null;
  state.detailItemId = "";
  state.llmSuggestions = [];
  state.executionSummary = null;
  renderPlan();
  setBusy("analyzing", true);
  if (mode === "ai") setBusy("requestingAi", true);
  setLoading(mode === "ai" ? "llm" : "analyze");
  showFeedback(mode === "ai" ? "AI 智能预览分析中" : "规则预览分析中", { type: "loading" });
  setStatus(mode === "ai" ? "AI 智能预览分析中" : "规则预览分析中", "loading");
  try {
    const response = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ root_path: root, recursive: true, preview_mode: mode }),
    });
    state.scan = response.scan;
    state.plan = response.plan;
    state.llmSuggestions = [];
    state.executionSummary = null;
    renderPlan();
    await Promise.all([
      loadRecentFolders().catch(() => {}),
      loadFolderPickerState().catch(() => {}),
    ]);
    if ((state.plan?.messages || []).includes("ai_preview_failed_fallback")) {
      toast("AI 建议失败，已回退到规则预览。", "warning");
      setStatus("AI 建议失败，已回退到规则预览。", "warning");
    } else {
      toast(mode === "ai" ? "AI 智能预览已生成" : "规则预览已生成", "success");
      setStatus(mode === "ai" ? "AI 智能预览已生成" : "规则预览已生成", "success");
    }
  } catch (error) {
    state.scan = previousScan;
    state.plan = previousPlan;
    renderPlan();
    toast(`分析失败：${error.message}`, "error");
    setStatus("分析失败", "error");
  } finally {
    setBusy("analyzing", false);
    if (mode === "ai") setBusy("requestingAi", false);
    setLoading("");
    renderPlan();
  }
}

async function scan() {
  const root = $("#rootPath").value.trim();
  if (!root) {
    toast("root_required");
    return;
  }
  setLoading("scan");
  try {
    state.scan = await api("/api/scan", {
      method: "POST",
      body: JSON.stringify({ root_path: root, recursive: true }),
    });
    state.plan = null;
    state.llmSuggestions = [];
    state.executionSummary = null;
    renderPlan();
    await loadRecentFolders().catch(() => {});
    toast(`scan_complete:${state.scan.total_files}`);
  } finally {
    setLoading("");
  }
}

async function plan() {
  if (!state.scan) {
    toast("no_plan");
    return;
  }
  setLoading("plan");
  try {
    state.plan = await api("/api/plans", {
      method: "POST",
      body: JSON.stringify({ scan_id: state.scan.scan_id }),
    });
    state.llmSuggestions = [];
    state.executionSummary = null;
    renderPlan();
    await loadRecentFolders().catch(() => {});
    toast("预览已生成");
  } finally {
    setLoading("");
  }
}

async function validatePlan() {
  if (!state.plan?.plan_id) {
    toast("no_plan", "warning");
    return;
  }
  if (isBusy("validating")) return;
  setBusy("validating", true);
  setLoading("validate");
  showFeedback("校验中", { type: "loading" });
  setStatus("校验中", "loading");
  try {
    state.plan = await api(`/api/plans/${state.plan.plan_id}/validate`, { method: "POST" });
    state.executionSummary = null;
    renderPlan();
    toast("校验完成", "success");
    setStatus("校验完成", "success");
  } finally {
    setBusy("validating", false);
    setLoading("");
  }
}

async function updateSelection(mode, itemIds = []) {
  if (!state.plan?.plan_id) {
    toast("no_plan", "warning");
    return;
  }
  if (isBusy("updatingSelection")) return;
  setBusy("updatingSelection", true);
  try {
    const response = await api(`/api/plans/${state.plan.plan_id}/selection`, {
      method: "PATCH",
      body: JSON.stringify({ mode, selected_item_ids: itemIds }),
    });
    state.plan.plan_hash = response.plan_hash;
    state.plan.summary = response.summary;
    state.plan.items = response.items || state.plan.items.map((item) => ({
      ...item,
      selected: response.selected_item_ids.includes(item.id),
      checked: response.selected_item_ids.includes(item.id),
    }));
    renderPlan();
    setStatus("选择已更新", "success");
  } finally {
    setBusy("updatingSelection", false);
  }
}

async function selectSafeItems() {
  state.executionSummary = null;
  await updateSelection("select_safe", []);
  toast("已选择安全项", "success");
}

async function clearSelection() {
  state.executionSummary = null;
  await updateSelection("replace", []);
  toast("已清空选择", "success");
}

function renderExecutionSummary(response) {
  const target = $("#executionSummaryResult");
  if (!target) return;
  const messages = (response.messages || []).map((code) => `- ${friendlyCode(code)} (${code})`).join("\n") || "- 无阻止消息";
  target.textContent = [
    `可以执行: ${response.ok_to_execute ? "是" : "否"}`,
    `选中: ${response.selected_count}`,
    `改名: ${response.rename_count}`,
    `隔离: ${response.quarantine_count}`,
    `关联文件: ${response.sidecar_count}`,
    `阻止: ${response.blocking_count}`,
    `警告: ${response.warning_count}`,
    `需复核: ${response.requires_review_count}`,
    "消息:",
    messages,
  ].join("\n");
}

function executionReportFromResponse(response) {
  const items = response.items || [];
  const renamed = items.filter((item) => item.operation === "rename" && item.state === "renamed").length;
  const quarantined = items.filter((item) => item.operation === "quarantine" && item.state === "quarantined").length;
  const skipped = items.filter((item) => item.state === "skipped").length;
  const failed = items.filter((item) => item.state === "failed" || item.state === "rollback_failed").length;
  return {
    run_id: response.run_id,
    state: response.state || "",
    renamed,
    quarantined,
    skipped,
    failed,
    rollback_available: renamed + quarantined > 0,
    failed_items: items.filter((item) => item.state === "failed" || item.state === "rollback_failed"),
  };
}

function renderExecutionReport() {
  const panel = $("#executionReportPanel");
  if (!panel) return;
  const report = state.executionReport;
  panel.hidden = !report;
  if (!report) return;
  setText("#executionReportRunId", report.run_id || "-");
  setText("#executionReportState", friendlyCode(report.state || "-"));
  setText("#executionReportRenamed", report.renamed);
  setText("#executionReportQuarantined", report.quarantined);
  setText("#executionReportSkipped", report.skipped);
  setText("#executionReportFailed", report.failed);
  setText("#executionReportRollback", report.rollback_available ? "可回滚" : "无可回滚项");
  const failedList = $("#executionReportFailedItems");
  if (failedList) {
    failedList.innerHTML = "";
    if (!report.failed_items.length) {
      const li = document.createElement("li");
      li.textContent = "无失败项";
      failedList.append(li);
    } else {
      for (const item of report.failed_items) {
        const li = document.createElement("li");
        li.textContent = `${item.plan_item_id || item.id || "-"}：${friendlyMessage(item.message || item.issue_code || "failed")}`;
        failedList.append(li);
      }
    }
  }
}

async function showExecutionSummary() {
  if (!state.plan?.plan_id) {
    toast("no_plan", "warning");
    return null;
  }
  showFeedback("正在读取执行摘要", { type: "loading" });
  const selected = selectedExecutableItems();
  const response = await api(`/api/plans/${state.plan.plan_id}/execution-summary`, {
    method: "POST",
    body: JSON.stringify({
      selected_item_ids: selected.map((item) => item.id),
      plan_hash: state.plan.plan_hash,
    }),
  });
  state.executionSummary = response;
  renderExecutionSummary(response);
  updateSummary();
  toast("执行摘要已加载", response.ok_to_execute ? "success" : "warning");
  setStatus("执行摘要已加载", response.ok_to_execute ? "success" : "warning");
  return response;
}

function llmReviewItemIds() {
  const selected = selectedExecutableItems().map((item) => item.id);
  if (selected.length) return selected;
  return (state.plan?.items || [])
    .filter((item) => item.requires_review || item.action === "review")
    .map((item) => item.id);
}

async function previewLlmPayload() {
  if (!state.plan?.plan_id) {
    toast("no_plan");
    return;
  }
  const itemIds = llmReviewItemIds();
  if (!itemIds.length) {
    toast("no_llm_items");
    return;
  }
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/payload-preview`, {
    method: "POST",
    body: JSON.stringify({ item_ids: itemIds, include_neighbors: true }),
  });
  const target = $("#executionSummaryResult");
  if (target) target.textContent = JSON.stringify(response, null, 2);
}

async function loadLlmSuggestions() {
  if (!state.plan?.plan_id) return;
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggestions`);
  state.llmSuggestions = response.suggestions || [];
}

async function exportPlanJson() {
  if (!state.plan?.plan_id) {
    toast("no_plan", "warning");
    return;
  }
  if (isBusy("exporting")) return;
  setBusy("exporting", true);
  showFeedback("正在导出 JSON", { type: "loading" });
  try {
    const response = await api(`/api/plans/${state.plan.plan_id}/export.json`);
    const text = JSON.stringify(response, null, 2);
    const target = $("#executionSummaryResult");
    if (target) target.textContent = text;
    downloadText(`${state.plan.plan_id}.json`, text, "application/json");
    toast("导出完成", "success");
    setStatus("导出完成", "success");
  } finally {
    setBusy("exporting", false);
  }
}

async function exportPlanCsv() {
  if (!state.plan?.plan_id) {
    toast("no_plan", "warning");
    return;
  }
  if (isBusy("exporting")) return;
  setBusy("exporting", true);
  showFeedback("正在导出 CSV", { type: "loading" });
  try {
    const response = await apiText(`/api/plans/${state.plan.plan_id}/export.csv`);
    const target = $("#executionSummaryResult");
    if (target) target.textContent = response;
    downloadText(`${state.plan.plan_id}.csv`, response, "text/csv");
    toast("导出完成", "success");
    setStatus("导出完成", "success");
  } finally {
    setBusy("exporting", false);
  }
}

async function llmSuggest() {
  if (!state.plan?.plan_id) {
    toast("no_plan");
    return;
  }
  const itemIds = llmReviewItemIds();
  if (!itemIds.length) {
    toast("no_llm_items");
    return;
  }
  setLoading("llm");
  try {
    const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggest`, {
      method: "POST",
      body: JSON.stringify({
        item_ids: itemIds,
        include_neighbors: true,
        use_cache: true,
      }),
    });
    state.llmSuggestions = response.suggestions || [];
    renderPlan();
    toast(`llm_suggestions:${response.suggestions.length}`);
  } finally {
    setLoading("");
  }
}

async function acceptLlmSuggestion(suggestion) {
  if (!state.plan?.plan_id) return;
  state.executionSummary = null;
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggestions/${suggestion.suggestion_id}/accept`, {
    method: "POST",
    body: JSON.stringify({ expected_plan_hash: state.plan.plan_hash }),
  });
  state.plan.plan_hash = response.plan_hash;
  state.plan.summary = response.summary;
  const itemIndex = state.plan.items.findIndex((item) => item.id === response.item.id);
  if (itemIndex >= 0) state.plan.items[itemIndex] = response.item;
  await loadLlmSuggestions();
  renderPlan();
}

async function rejectLlmSuggestion(suggestion) {
  if (!state.plan?.plan_id) return;
  await api(`/api/plans/${state.plan.plan_id}/llm/suggestions/${suggestion.suggestion_id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason_code: "user_rejected" }),
  });
  await loadLlmSuggestions();
  renderPlan();
}

async function executeSelected() {
  const buttonState = getExecuteButtonState();
  if (!buttonState.enabled) {
    toast(buttonState.reason, "warning");
    return;
  }
  if (isBusy("executing")) return;
  setBusy("executing", true);
  setLoading("execute");
  showFeedback("执行中", { type: "loading" });
  setStatus("执行中", "loading");
  try {
    const selected = selectedExecutableItems();
    const summary = await showExecutionSummary();
    if (!summary?.ok_to_execute) {
      toast("blocking_item_selected", "error");
      setStatus("执行被阻止", "error");
      return;
    }
    if (!window.confirm(`将执行 ${summary.selected_count} 项。执行前已完成摘要检查，是否继续？`)) return;
    const response = await api(`/api/plans/${state.plan.plan_id}/execute`, {
      method: "POST",
      body: JSON.stringify({
        selected_item_ids: selected.map((item) => item.id),
        confirm: true,
        plan_hash: state.plan.plan_hash,
      }),
    });
    state.executionReport = executionReportFromResponse(response);
    renderExecutionReport();
    toast("执行完成", "success");
    setStatus("执行完成", "success");
    await refreshRuns();
    await analyze();
  } catch (error) {
    toast(`执行失败：${error.message}`, "error");
    setStatus("执行失败", "error");
  } finally {
    setBusy("executing", false);
    setLoading("");
  }
}

function runMatchesFilter(run) {
  const stateCode = String(run.state || run.status || "");
  if (state.runFilter === "success") return stateCode === "success";
  if (state.runFilter === "partial_success") return stateCode === "partial_success";
  if (state.runFilter === "failed") return stateCode === "failed";
  if (state.runFilter === "rolled_back") return stateCode === "rolled_back";
  if (state.runFilter === "rollback_available") return Boolean(run.rollback_available);
  if (state.runFilter === "interrupted") return stateCode === "interrupted";
  return true;
}

function runSummaryText(run) {
  const summary = run.summary || {};
  const success = (summary.renamed || 0) + (summary.quarantined || 0) + (summary.skipped || 0);
  return `成功 ${success} / 失败 ${summary.failed || 0}`;
}

function renderRunSummaryCards() {
  const target = $("#runSummaryCards");
  if (!target) return;
  const runs = state.runs || [];
  const counts = {
    total: runs.length,
    success: runs.filter((run) => run.state === "success").length,
    partial_success: runs.filter((run) => run.state === "partial_success").length,
    failed: runs.filter((run) => run.state === "failed").length,
    rollback_available: runs.filter((run) => run.rollback_available).length,
  };
  const cards = [
    ["总批次", counts.total, "all"],
    ["成功", counts.success, "success"],
    ["部分成功", counts.partial_success, "partial_success"],
    ["失败", counts.failed, "failed"],
    ["可回滚", counts.rollback_available, "rollback_available"],
  ];
  target.innerHTML = "";
  for (const [label, value, filter] of cards) {
    const button = document.createElement("button");
    button.className = "metric-card compact";
    button.dataset.runFilter = filter;
    button.innerHTML = `<strong>${value}</strong><span>${label}</span>`;
    button.addEventListener("click", () => {
      state.runFilter = filter;
      const select = $("#runFilterSelect");
      if (select) select.value = filter;
      renderRunsTable();
    });
    target.append(button);
  }
}

function renderRunFilters() {
  const select = $("#runFilterSelect");
  if (!select) return;
  const options = [
    ["all", "全部"],
    ["success", "成功"],
    ["partial_success", "部分成功"],
    ["failed", "失败"],
    ["rolled_back", "已回滚"],
    ["rollback_available", "可回滚"],
    ["interrupted", "中断"],
  ];
  select.innerHTML = "";
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.append(option);
  }
  select.value = state.runFilter;
}

function renderRunsTable() {
  renderRunSummaryCards();
  renderRunFilters();
  const body = $("#runsBody");
  if (!body) return;
  const runs = (state.runs || []).filter(runMatchesFilter);
  body.innerHTML = "";
  if (!runs.length) {
    const row = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = "没有匹配的历史记录。";
    row.append(td);
    body.append(row);
    return;
  }
  for (const run of runs) {
    const detailButton = document.createElement("button");
    detailButton.className = "icon-btn";
    detailButton.textContent = "i";
    detailButton.title = "查看详情";
    detailButton.setAttribute("aria-label", "查看详情");
    detailButton.addEventListener("click", () => loadRunDetail(run.run_id).catch((error) => toast(error.message)));
    const row = document.createElement("tr");
    row.className = state.selectedRun?.run_id === run.run_id ? "selected-row" : "";
    row.addEventListener("click", (event) => {
      if (event.target instanceof HTMLButtonElement) return;
      loadRunDetail(run.run_id).catch((error) => toast(error.message));
    });
    row.append(
      cellText(run.run_id),
      cellText(run.timestamp || run.created_at || ""),
      cellText(friendlyCode(run.state || run.status)),
      cellText(run.rollback_available ? "可回滚" : "否"),
      cellText(runSummaryText(run)),
      cell(detailButton)
    );
    body.append(row);
  }
}

function renderRunDetail() {
  const panel = $("#runDetailPanel");
  if (!panel) return;
  const run = state.selectedRun;
  panel.hidden = !run;
  if (!run) return;
  setText("#runDetailId", run.run_id);
  setText("#runDetailState", friendlyCode(run.state));
  setText("#runDetailTime", `${run.created_at || "-"} / ${run.completed_at || "-"}`);
  setText("#runDetailCounts", `选中 ${run.selected_count}，成功 ${run.success_count}，失败 ${run.failed_count}`);
  setText("#runDetailRollback", run.rollback_available ? "可回滚" : friendlyCode(run.rollback_state));
  const body = $("#runDetailItemsBody");
  if (!body) return;
  body.innerHTML = "";
  for (const item of run.items || []) {
    const codes = [...(item.issue_codes || []), item.rollback_error_code].filter(Boolean);
    const row = document.createElement("tr");
    row.append(
      cellText(item.operation),
      cellText(friendlyCode(item.status)),
      cellText(item.source_name, "name-col"),
      cellText(item.target_name, "target-col"),
      cellText(codes.map((code) => `${friendlyCode(code)}(${code})`).join("; ")),
      cellText(item.rollback_status ? friendlyCode(item.rollback_status) : "-")
    );
    body.append(row);
  }
}

function renderRollbackPreview(preview) {
  const target = $("#runRollbackPreviewResult");
  if (!target) return;
  const rows = (preview.items || []).map((item) => {
    const codes = (item.issue_codes || []).map((code) => `${friendlyCode(code)}(${code})`).join("; ") || "-";
    return `${item.item_id} | ${item.rollback_action} | 当前:${item.current_path_status} | 目标:${item.restore_target_status} | 阻塞:${item.blocking ? "是" : "否"} | ${codes}`;
  });
  target.textContent = [
    `可以回滚: ${preview.ok_to_rollback ? "是" : "否"}`,
    `总项: ${preview.summary?.total_items || 0}`,
    `阻塞: ${preview.summary?.blocking_items || 0}`,
    `缺失: ${preview.summary?.missing_items || 0}`,
    `冲突: ${preview.summary?.conflict_items || 0}`,
    ...rows,
  ].join("\n");
}

async function loadRunDetail(runId) {
  if (!runId) {
    toast("run_not_found", "warning");
    return;
  }
  if (isBusy("loadingHistory")) return;
  setBusy("loadingHistory", true);
  try {
    state.selectedRun = await api(`/api/runs/${runId}`);
    state.rollbackPreview = null;
    renderRunsTable();
    renderRunDetail();
    setStatus("历史详情已加载", "success");
  } finally {
    setBusy("loadingHistory", false);
  }
}

async function previewSelectedRunRollback(runId = state.selectedRun?.run_id) {
  if (!runId) {
    toast("run_not_found", "warning");
    return null;
  }
  showFeedback("正在生成回滚预览", { type: "loading" });
  state.rollbackPreview = await api(`/api/runs/${runId}/rollback-preview`, {
    method: "POST",
    body: JSON.stringify({ item_ids: null }),
  });
  renderRollbackPreview(state.rollbackPreview);
  toast("回滚预览已生成", state.rollbackPreview.ok_to_rollback ? "success" : "warning");
  setStatus("回滚预览已生成", state.rollbackPreview.ok_to_rollback ? "success" : "warning");
  return state.rollbackPreview;
}

async function rollbackSelectedRun(runId = state.selectedRun?.run_id) {
  if (!runId) {
    toast("run_not_found", "warning");
    return;
  }
  if (isBusy("rollingBack")) return;
  setBusy("rollingBack", true);
  setLoading("rollback");
  showFeedback("回滚中", { type: "loading" });
  setStatus("回滚中", "loading");
  try {
    const preview = await previewSelectedRunRollback(runId);
    if (!preview?.ok_to_rollback) {
      toast("rollback_not_available", "warning");
      return;
    }
    if (!window.confirm(`将回滚 ${preview.summary.rollbackable_items} 项，是否继续？`)) return;
    const response = await api(`/api/runs/${runId}/rollback`, {
      method: "POST",
      body: JSON.stringify({ item_ids: null }),
    });
    toast("回滚完成", "success");
    setStatus("回滚完成", "success");
    await refreshRuns();
    await loadRunDetail(runId);
  } catch (error) {
    toast(`回滚失败：${error.message}`, "error");
    setStatus("回滚失败", "error");
  } finally {
    setBusy("rollingBack", false);
    setLoading("");
  }
}

async function exportSelectedRunJson(runId = state.selectedRun?.run_id) {
  if (!runId) {
    toast("run_not_found", "warning");
    return;
  }
  if (isBusy("exporting")) return;
  setBusy("exporting", true);
  try {
    const response = await api(`/api/runs/${runId}/export.json`);
    downloadText(`${runId}-report.json`, JSON.stringify(response, null, 2), "application/json");
    toast("导出完成", "success");
    setStatus("导出完成", "success");
  } finally {
    setBusy("exporting", false);
  }
}

async function exportSelectedRunCsv(runId = state.selectedRun?.run_id) {
  if (!runId) {
    toast("run_not_found", "warning");
    return;
  }
  if (isBusy("exporting")) return;
  setBusy("exporting", true);
  try {
    const response = await apiText(`/api/runs/${runId}/export.csv`);
    downloadText(`${runId}-report.csv`, response, "text/csv");
    toast("导出完成", "success");
    setStatus("导出完成", "success");
  } finally {
    setBusy("exporting", false);
  }
}

async function refreshRuns() {
  if (isBusy("loadingHistory")) return;
  setBusy("loadingHistory", true);
  try {
    state.runs = await api("/api/runs");
    renderRunsTable();
  } finally {
    setBusy("loadingHistory", false);
  }
}

async function loadDiagnostics() {
  if (isBusy("loadingDiagnostics")) return;
  setBusy("loadingDiagnostics", true);
  setLoading("diagnostics");
  try {
    state.diagnostics = await api("/api/diagnostics");
    renderDiagnosticsSummary(state.diagnostics);
    const target = $("#diagnosticsResult");
    if (target) target.textContent = JSON.stringify(state.diagnostics, null, 2);
    updateSummary();
  } finally {
    setBusy("loadingDiagnostics", false);
    setLoading("");
  }
}

async function copyDiagnostics() {
  if (!state.diagnostics) await loadDiagnostics();
  const text = JSON.stringify(state.diagnostics, null, 2);
  await navigator.clipboard.writeText(text);
  toast("诊断 JSON 已复制", "success");
  setStatus("诊断 JSON 已复制", "success");
}

function setupTabs() {
  for (const button of document.querySelectorAll(".nav-tabs button[data-tab]")) {
    button.addEventListener("click", () => {
      for (const item of document.querySelectorAll(".nav-tabs button[data-tab]")) item.classList.remove("active");
      for (const panel of document.querySelectorAll(".panel")) panel.classList.remove("active");
      button.classList.add("active");
      document.querySelector(`[data-panel="${button.dataset.tab}"]`).classList.add("active");
      if (button.dataset.tab === "settings" && !state.diagnostics) {
        loadDiagnostics().catch((error) => toast(error.message));
      }
    });
  }
}

function setupSettingsTabs() {
  const buttons = document.querySelectorAll("[data-settings-tab]");
  const panels = document.querySelectorAll("[data-settings-panel]");
  const activate = (tab) => {
    state.settingsTab = tab || "llm";
    for (const button of buttons) {
      button.classList.toggle("active", button.dataset.settingsTab === state.settingsTab);
      button.setAttribute("aria-pressed", button.dataset.settingsTab === state.settingsTab ? "true" : "false");
    }
    for (const panel of panels) {
      panel.hidden = panel.dataset.settingsPanel !== state.settingsTab;
    }
  };
  for (const button of buttons) {
    button.addEventListener("click", () => activate(button.dataset.settingsTab));
  }
  activate(state.settingsTab);
}

function setupReviewControls() {
  for (const card of document.querySelectorAll("[data-filter]")) {
    card.addEventListener("click", () => {
      state.filter = card.dataset.filter || "all";
      const filter = $("#filterSelect");
      if (filter) filter.value = state.filter;
      renderPlan();
    });
  }
}

function bindClick(selector, handler) {
  const node = $(selector);
  if (node) node.addEventListener("click", () => handler().catch((error) => {
    toast(error.message, "error");
    setStatus(error.message, "error");
  }));
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupSettingsTabs();
  setupReviewControls();
  $("#filterSelect")?.addEventListener("change", () => {
    state.filter = $("#filterSelect").value;
    renderPlan();
  });
  $("#runFilterSelect")?.addEventListener("change", () => {
    state.runFilter = $("#runFilterSelect").value;
    renderRunsTable();
  });
  $("#llmCompatibilityMode")?.addEventListener("change", updateLlmModeHelp);
  for (const button of document.querySelectorAll("[data-preview-mode]")) {
    button.addEventListener("click", () => {
      state.previewMode = button.dataset.previewMode || "rule";
      renderPreviewModeControls();
    });
  }
  bindClick("#folderPickerBtn", chooseFolder);
  bindClick("#analyzeBtn", analyze);
  bindClick("#scanBtn", scan);
  bindClick("#planBtn", plan);
  bindClick("#validateBtn", validatePlan);
  bindClick("#llmBtn", llmSuggest);
  bindClick("#executeBtn", executeSelected);
  bindClick("#selectSafeBtn", selectSafeItems);
  bindClick("#clearSelectionBtn", clearSelection);
  bindClick("#exportPlanJsonBtn", exportPlanJson);
  bindClick("#exportPlanCsvBtn", exportPlanCsv);
  bindClick("#executionSummaryBtn", showExecutionSummary);
  bindClick("#previewLlmPayloadBtn", previewLlmPayload);
  bindClick("#refreshRunsBtn", refreshRuns);
  bindClick("#runRollbackPreviewBtn", () => previewSelectedRunRollback());
  bindClick("#runRollbackBtn", () => rollbackSelectedRun());
  bindClick("#runExportJsonBtn", () => exportSelectedRunJson());
  bindClick("#runExportCsvBtn", () => exportSelectedRunCsv());
  bindClick("#viewLastRunBtn", () => loadRunDetail(state.executionReport?.run_id));
  bindClick("#previewLastRollbackBtn", () => previewSelectedRunRollback(state.executionReport?.run_id));
  bindClick("#exportLastRunReportBtn", () => exportSelectedRunJson(state.executionReport?.run_id));
  bindClick("#clearRecentFoldersBtn", clearRecentFolders);
  bindClick("#saveSettingsBtn", saveSettings);
  bindClick("#testLlmBtn", testLlm);
  bindClick("#testRuleBtn", testRules);
  bindClick("#exportSettingsBtn", exportSettings);
  bindClick("#importSettingsDryRunBtn", () => importSettings(true));
  bindClick("#applyImportSettingsBtn", () => importSettings(false));
  bindClick("#firstRunDismissBtn", dismissFirstRunHelper);
  bindClick("#refreshDiagnosticsBtn", loadDiagnostics);
  bindClick("#copyDiagnosticsBtn", copyDiagnostics);
  await loadCapabilities().catch(() => {});
  await loadSettings().catch((error) => toast(error.message));
  await loadDiagnostics().catch(() => {});
  await loadFolderPickerState().catch(() => {});
  await loadRecentFolders().catch(() => {});
  await refreshRuns().catch(() => {});
  renderPlan();
  renderExecutionReport();
});

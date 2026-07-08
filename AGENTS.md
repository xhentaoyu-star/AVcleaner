# AVcleaner Agent Notes

- 用户没有代码经验，沟通时说人话，直接完成工作，不把改文件或运行命令交给用户。
- 代码任务先用 CodeGraph 看结构、流程、调用关系和影响面；CodeGraph 没覆盖的模板、CSS、JS、文档和配置再用普通读取。
- 前端保持 Jinja2 模板、静态 CSS、静态 app.js，不引入 React/Vue/Svelte，不用 CDN 或运行时网络资源。
- AVcleaner 的安全模型不能削弱：旧 `/api/execute` 和通用 `/api/llm/suggest` 必须保持 HTTP 410；执行只接受 `selected_item_ids`、`confirm`、`plan_hash`；后端计划和校验始终权威。
- LLM 只做预览建议，不能执行文件，不能绕过 Pydantic、canonical schema 或 `validators.py`，默认不发送完整本机路径。
- 不做刮削、封面下载、NFO、最终媒体库移动、演员/片商/分类整理、OpenAver 数据库集成或安装器。
- 使用媒体文件搭程序时，复制媒体文件的同时改成英文文件名。
- 修改后用真实命令验证，优先运行项目现有检查脚本。

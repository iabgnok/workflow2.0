## 1. 项目依赖配置

- [x] 1.1 在 `pyproject.toml` 中添加 `pydantic-settings>=2.0` 依赖
- [x] 1.2 运行 `uv sync` 安装依赖并更新 `uv.lock`

## 2. Settings 模块实现

- [x] 2.1 创建 `new_src/config/__init__.py`
- [x] 2.2 创建 `new_src/config/settings.py`，实现 Settings(BaseSettings) 类，包含所有 LLM 配置字段
- [x] 2.3 添加引擎参数字段（context_window_tokens、soft/hard ratio、soft_reset_max_history）
- [x] 2.4 添加路径配置字段（db_path、workflows_root、skills_root、prompts_root）
- [x] 2.5 添加 default_workflow_inputs 字段（dict 类型，含 5 个默认值）
- [x] 2.6 配置 model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)
- [x] 2.7 在文件末尾创建模块级单例 `settings = Settings()`

## 3. 环境配置文件

- [x] 3.1 更新 `.env.example`，列出所有支持的环境变量及其默认值说明

## 4. 验证测试

- [x] 4.1 编写单元测试：验证 Settings 类的默认值正确
- [x] 4.2 编写单元测试：验证环境变量能正确覆盖默认值
- [x] 4.3 编写单元测试：验证 default_workflow_inputs 字段结构
- [x] 4.4 编写单元测试：验证路径字段空字符串行为

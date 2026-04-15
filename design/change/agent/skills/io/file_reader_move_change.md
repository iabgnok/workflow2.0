# skills/io/file_reader.py（从 atomic/file_reader.py 迁移）

## 一、整体现状评估

当前实现是所有 skill 里最简陋的：用 print 而不是 logger，execute(text, context) 是同步方法，直接从 context.get('file_path') 取值（不读 step 的 input mapping），缺失时返回空 dict。

## 二、继承 IOSkillSpec，声明元数据

类变量：

name = "file_reader"
description = "读取本地文件内容，返回文本字符串"
when_to_use = "需要读取文件、配置、模板等本地资源时"
do_not_use_when = "需要写入、修改或删除文件（使用 file_writer）"
idempotency = IdempotencyLevel.L0（只读，强幂等）
retry_policy = ErrorPolicy(max_retries=3, backoff_base=2.0, action_on_exhaust=FailureAction.CONFIRM)

## 三、接口统一为 execute_step

新增 execute_step(step, context) 作为主入口（async），execute 方法标注为 deprecated 保留向后兼容。
变量读取方式改变：不再直接 context.get('file_path')，而是从 step['inputs'] 的映射里找到 file_path 对应的 context key，再去 context 里取值。这是正确的方式——step 的 inputs 声明了"我需要什么变量，对应 context 里的哪个 key"，skill 应该遵守这个声明。
具体：input_mapping = step.get('inputs', {})，找到 key 为 file_path（或 step 声明的任何 key）的条目，取其 value（即 context 里的 key 名），再 context.get(that_key) 拿到实际文件路径。
保持文件路径不存在时的行为：FileNotFoundError 直接向上传播，让 error_policy 的重试机制处理。
print 改为 logger，统一日志格式。
encoding fallback：现有硬编码 encoding='utf-8'，读取失败不尝试其他编码。重构后先尝试 utf-8，失败（UnicodeDecodeError）时再尝试 gbk 或 latin-1，返回时附带 "encoding_used" 字段。[待定：是否需要 encoding fallback，还是明确只支持 utf-8，让用户在文件路径里处理]
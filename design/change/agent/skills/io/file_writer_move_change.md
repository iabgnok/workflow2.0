# skills/io/file_writer.py（从 atomic/file_writer.py 迁移）

## 一、整体现状评估

当前实现是最差的：同步 execute 方法，内部有一段手动的 {{var}} 变量替换逻辑（content.replace(f"{{{{{k}}}}}", str(v))）——这个替换在 Runner 里已经做过了，这里是多余的二次替换，而且用的是不安全的逐个 str.replace，正是 parser 已修复的那个 bug 的源头。

## 二、继承 IOSkillSpec，声明元数据

类变量：

name = "file_writer"
description = "将内容写入本地文件，如果目录不存在则自动创建"
when_to_use = "需要保存生成结果、日志或任何文本内容到文件时"
idempotency = IdempotencyLevel.L1（写文件有副作用，但相同内容写入同一文件可以接受，条件幂等）
retry_policy = ErrorPolicy(max_retries=2, backoff_base=2.0, action_on_exhaust=FailureAction.CONFIRM)

## 三、接口统一和内部清洁

新增 execute_step(step, context) 作为主入口（async），删除 execute 里的手动变量替换逻辑（Runner/StepExecutor 已经在调用前做了变量注入）。
从 step.inputs 里读 content 和 file_path：和 file_reader 同样的原则，从 step 的 input mapping 里找对应的 context key，不直接硬编码 key 名。

**``` ```content代码块解析**：保持现有正则提取 *``` ```content代码块*的逻辑，但把手动变量替换删掉（变量已经在 StepExecutor 里通过replace_variables 注入过了）。
目录自动创建：现有实现没有，新增 os.makedirs(os.path.dirname(file_path), exist_ok=True)，避免目标目录不存在时崩溃。
返回值增加 written_file_path：现有只返回 {"file_writer_status": "Success"}。重构后返回 {"file_writer_status": "success", "written_file_path": file_path}，多一个可用的输出变量。
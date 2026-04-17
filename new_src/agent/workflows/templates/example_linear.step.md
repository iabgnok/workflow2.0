---
version: 2.0
name: Example Linear Workflow
description: 三步线性流少样本示例：读取文件 → LLM 处理 → 写入结果。
inputs:
  - file_path
  - target_file
outputs:
  - file_writer_status
---

## Step 1: 读取输入文件
**Action**: `file_reader`
**Input**:
- file_path
**Output**:
- file_content

## Step 2: LLM 处理内容
**Action**: `llm_prompt_call`
**Input**:
- file_content
**Output**:
- llm_output

```prompt
请对以下内容进行简洁总结：

{{file_content}}
```

## Step 3: 写入结果文件
**Action**: `file_writer`
**Input**:
- llm_output
- target_file
**Output**:
- file_writer_status
- written_file_path

```content
{{llm_output}}
```

# protocol/error_codes.py 重构实现细节

## 一、整体保持

所有现有错误码保持不变，分组也保持不变。这是已被测试覆盖的稳定接口，不需要改动。

## 二、可能新增的错误码

如果方向一落地后 WorkflowModel.from_structured_artifact() 适配失败，需要一个新的错误码：WF_STRUCTURED_ARTIFACT_INVALID = "WF_STRUCTURED_ARTIFACT_INVALID"，加入 GATEKEEPER_ISSUE_CODES 分组。[待定：是否需要，取决于方向一落地时的具体实现]
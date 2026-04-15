# protocol/errors.py 重构实现细节

## 一、整体保持

现有五个异常类设计简洁合理，保持不变：ProtocolError（基类）、ProtocolSchemaError、ProtocolGatekeeperError、ProtocolDryRunError、ProtocolRuntimeValidationError。

## 二、新增异常（可选）

EscalationLimitExceeded：目前建议放在这里（协议层异常），也可以放在 engine/errors.py。这个异常在 Runner 主循环里被 raise，是执行层的概念，放在 engine/errors.py 更合理。[待定：engine/errors.py 是否新建]
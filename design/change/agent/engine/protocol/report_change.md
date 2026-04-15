# protocol/report.py 重构实现细节

## 一、整体保持

ProtocolIssue、ProtocolReport 设计合理，保持不变。

## 二、新增 to_defect_dict() 方法到 ProtocolIssue

如 gatekeeper 分析里所述，新增此方法，输出格式：

   {
     "location": self.location or "workflow",
     "type": "PROTOCOL_ERROR",
     "reason": self.message,
     "suggestion": self.suggestion or ""
   }
供 ChampionTracker 把协议层错误回流给 Generator 时使用。

## 三、新增 errors_as_defects() 到 ProtocolReport

返回 list[dict]，把 report 里所有 error 级别的 issue 转换为 defect dict 格式（调用 issue.to_defect_dict()），供批量回流使用。这是协议层错误回流到 Generator 的关键接口。
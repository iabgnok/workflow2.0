# orchestration/ 目录

整体说明

这是全新目录，只有一个文件。来源：把 Runner 里 18 个方法里的 8 个 Champion 相关方法整体拆出，通过 ExecutionHooks 接口接入 Runner，使引擎本体对 Meta Workflow 业务逻辑完全无感知。

orchestration/ 新增文件汇总：champion_tracker.py（继承 ExecutionHooks，覆盖四个 hook，承接 Runner 的 12 个方法）
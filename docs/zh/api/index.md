# API 参考（自动生成）

`hiveflow` 包中选定公开符号的参考文档。教程请参阅 [快速入门](../getting-started.md)。

## Core 引擎

::: hiveflow.HiveFlow
    options:
      show_root_heading: true
      members:
        - start
        - shutdown
        - create_agent
        - set_strategy

::: hiveflow.HiveFlowConfig

## 消息传递

::: hiveflow.ECM

## Human-in-the-loop

::: hiveflow.HITLManager
    options:
      members:
        - create_gate
        - respond
        - list_pending_gates

::: hiveflow.HITLAction

## Scheduler（调度器）

::: hiveflow.InProcessScheduler
    options:
      members:
        - schedule

## 完整手动参考

旧版手写表格仍保留在 [api-reference.md](../api-reference.md)，直至所有模块迁移至 mkdocstrings。

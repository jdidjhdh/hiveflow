# API Reference (auto-generated)

Reference for selected public symbols in the `hiveflow` package. For tutorials see [Getting Started](../getting-started.md).

## Core engine

::: hiveflow.HiveFlow
    options:
      show_root_heading: true
      members:
        - start
        - shutdown
        - create_agent
        - set_strategy

::: hiveflow.HiveFlowConfig

## Messaging

::: hiveflow.ECM

## Human-in-the-loop

::: hiveflow.HITLManager
    options:
      members:
        - create_gate
        - respond
        - list_pending_gates

::: hiveflow.HITLAction

## Scheduler

::: hiveflow.InProcessScheduler
    options:
      members:
        - schedule

## Full manual reference

Legacy hand-written tables remain in [api-reference.md](../api-reference.md) until all modules are migrated to mkdocstrings.

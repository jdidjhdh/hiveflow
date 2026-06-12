# Multi-Agent Debate

Pattern: multiple specialist agents write to the blackboard; a synthesizer agent produces the final answer.

## When to use

- Research tasks needing diverse perspectives
- Red-team / blue-team review before publication

## Architecture

```
Intent → Scheduler → [Researcher, Critic, FactChecker] (parallel)
                              ↓ blackboard keys
                     Synthesizer → final.result
```

## Example

Run [examples/02_multi_agent.py](https://github.com/jdidjhdh/hiveflow/blob/main/examples/02_multi_agent.py):

```bash
cd packages/core && pip install -e ".[all]"
python ../../examples/02_multi_agent.py
```

Key ideas:

1. Each agent has disjoint `write_keys` and shared read keys
2. Scheduler strategy (`LeastLoadedStrategy`, `AuctionStrategy`) picks workers
3. `SecureBlackboard` enforces key-level permissions

## Studio template

Load the **debate_decision** template from Orchestrator → Templates.

## Related

- [Concepts — Multi-Agent](../concepts.md)
- [Example 12 — custom scheduler](https://github.com/jdidjhdh/hiveflow/blob/main/examples/12_custom_scheduler.py)

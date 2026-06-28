"""
HiveFlow - 17: X/Twitter Source Review

This example shows how a TweetClaw/OpenClaw or Xquik MCP source can feed
public X/Twitter evidence into a HiveFlow workflow before a human approves
downstream use. Network calls are mocked so the example runs without
credentials.

Usage:
    python 17_x_twitter_source_review.py
"""
import asyncio

from hiveflow import ECM, HITLAction, HITLManager, HITLStatus, HiveFlow, HiveFlowConfig


SOURCE_ROWS = [
    {
        "url": "https://x.com/example/status/1001",
        "author": "@example_builder",
        "text": "Teams want more transparent agent approval steps.",
        "engagement": {"likes": 42, "reposts": 7},
    },
    {
        "url": "https://x.com/example/status/1002",
        "author": "@example_ops",
        "text": "Source packets should be reviewed before draft generation.",
        "engagement": {"likes": 31, "reposts": 5},
    },
]


async def main():
    hf = HiveFlow(HiveFlowConfig())
    hitl = HITLManager()
    await hf.start()

    try:
        print("=== X/Twitter Source Review Example ===\n")

        async def source_collector_handler(ecm, view):
            source_name = ecm.payload.get("source_name", "TweetClaw/OpenClaw source")
            source_packet = {
                "source_name": source_name,
                "query": ecm.payload.get("query", "agent approval workflows"),
                "rows": SOURCE_ROWS,
            }
            await view.put("x_source_packet", source_packet)
            print(f"  Collected {len(SOURCE_ROWS)} public X/Twitter rows from {source_name}")
            return {"rows": len(SOURCE_ROWS), "source_name": source_name}

        async def reviewer_handler(ecm, view):
            source_packet = await view.get("x_source_packet")
            gate = await hitl.create_gate(
                workflow_id=ecm.trace_id,
                node_id="x_source_review",
                action=HITLAction.APPROVAL,
                prompt="Review public X/Twitter source rows before draft generation",
                context={
                    "query": source_packet["query"],
                    "rows": source_packet["rows"],
                    "policy": "Use as source evidence only; do not publish automatically.",
                },
                timeout_seconds=300,
                on_timeout="fail",
            )
            print(f"  Review gate created: {gate.gate_id}")

            await hitl.respond(gate.gate_id, approved=True, comment="approved source packet")
            resolved = await hitl.wait_for_response(gate.gate_id)

            if resolved.status != HITLStatus.APPROVED:
                await view.put("approved_source_context", {"status": "rejected"})
                return {"status": "rejected"}

            approved_context = {
                "status": "approved",
                "reviewer": resolved.human_comment,
                "evidence_urls": [row["url"] for row in source_packet["rows"]],
                "next_step": "draft with citations, then request publish approval separately",
            }
            await view.put("approved_source_context", approved_context)
            print(f"  Approved {len(approved_context['evidence_urls'])} source URLs")
            return approved_context

        await hf.create_agent(
            agent_id="tweetclaw_source_collector",
            skills={"collect_x_sources"},
            read_keys=set(),
            write_keys={"x_source_packet"},
            task_handler=source_collector_handler,
        )
        await hf.create_agent(
            agent_id="source_reviewer",
            skills={"review_x_sources"},
            read_keys={"x_source_packet"},
            write_keys={"approved_source_context"},
            task_handler=reviewer_handler,
        )

        await hf.scheduler.schedule(
            ECM(
                trace_id="x-source-review-demo",
                intent="Collect public X/Twitter source rows",
                intent_id="collect-x-sources",
                emitter="user",
                required_skills=["collect_x_sources"],
                payload={"source_name": "TweetClaw/OpenClaw source"},
            )
        )
        await asyncio.sleep(0.3)

        await hf.scheduler.schedule(
            ECM(
                trace_id="x-source-review-demo",
                intent="Review source rows before content drafting",
                intent_id="review-x-sources",
                emitter="user",
                required_skills=["review_x_sources"],
            )
        )
        await asyncio.sleep(0.3)

        approved = await hf.blackboard.sys_get("approved_source_context")
        print(f"\nWorkflow completed: {approved}")

    finally:
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

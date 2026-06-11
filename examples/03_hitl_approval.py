"""
HiveFlow - 03: Human-in-the-Loop Approval

This example demonstrates how to integrate human approval into agent workflows.

Usage:
    python 03_hitl_approval.py
"""
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM, HITLManager, HITLAction


async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()

    try:
        print("=== Human-in-the-Loop Approval Example ===\n")

        async def content_creator_handler(ecm, view):
            content = {
                "title": "AI in 2025",
                "body": "Artificial Intelligence is transforming...",
                "author": ecm.emitter,
            }
            await view.put("content_draft", content)
            print(f"  Content created: {content['title']}")
            return content

        async def publisher_handler(ecm, view):
            draft = await view.get("content_draft")
            approval_status = await view.get("approval_status")

            if approval_status and approval_status.get("approved"):
                published = {**draft, "status": "published", "published_at": "2026-06-11"}
                await view.put("published_content", published)
                print(f"  Content published: {published['title']}")
                return published

            print("  Publication rejected")
            return {"status": "rejected"}

        print("Creating agents...")
        await hf.create_agent(
            agent_id="content_creator",
            skills={"write", "create"},
            read_keys=set(),
            write_keys={"content_draft"},
            task_handler=content_creator_handler,
        )
        await hf.create_agent(
            agent_id="publisher",
            skills={"publish"},
            read_keys={"content_draft", "approval_status"},
            write_keys={"published_content"},
            task_handler=publisher_handler,
        )
        print("  Agents ready")

        hitl = HITLManager()
        gate = await hitl.create_gate(
            workflow_id="hitl-demo-1",
            node_id="approval-node",
            action=HITLAction.APPROVAL,
            prompt="Please review and approve the content before publishing",
            context={"draft_title": "AI in 2025"},
            timeout_seconds=300,
            on_timeout="fail",
        )
        print(f"\nHITL gate created: {gate.gate_id}")

        print("\nStep 1: Creating content...")
        await hf.scheduler.schedule(ECM(
            trace_id="hitl-demo-1",
            intent="Create article about AI",
            intent_id="create-1",
            emitter="user",
            required_skills=["write"],
            payload={"topic": "AI"},
        ))
        await asyncio.sleep(0.3)

        print("\nStep 2: Human approval...")
        draft = await hf.blackboard.sys_get("content_draft")
        print(f"  Draft ready: {draft['title']}")
        await hitl.respond(gate.gate_id, approved=True, comment="approved by admin")
        resolved = await hitl.wait_for_response(gate.gate_id)
        print(f"  Gate status: {resolved.status.value}")

        await hf.blackboard.sys_put("approval_status", {"approved": True, "reviewer": "admin"})

        print("\nStep 3: Publishing...")
        await hf.scheduler.schedule(ECM(
            trace_id="hitl-demo-1",
            intent="Publish approved content",
            intent_id="publish-1",
            emitter="user",
            required_skills=["publish"],
        ))
        await asyncio.sleep(0.3)

        published = await hf.blackboard.sys_get("published_content")
        print(f"\nWorkflow completed: {published}")

    finally:
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

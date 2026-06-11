"""
HiveFlow - 02: Multi-Agent Collaboration

This example demonstrates how multiple agents collaborate to complete a complex task.

Usage:
    python 02_multi_agent.py
"""
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM


async def main():
    # 1. Create the engine
    config = HiveFlowConfig()
    hf = HiveFlow(config)

    # 2. Start the engine
    await hf.start()

    try:
        print("=== Multi-Agent Collaboration Example ===\n")

        # 3. Define agent handlers
        async def researcher_handler(ecm, view):
            """Research agent that searches and analyzes."""
            research_data = {
                "topic": ecm.payload.get("topic", "AI"),
                "findings": ["Finding 1", "Finding 2", "Finding 3"],
                "summary": f"Research on {ecm.payload.get('topic', 'AI')} completed"
            }
            await view.put("research_results", research_data)
            return research_data

        async def writer_handler(ecm, view):
            """Writer agent that creates content."""
            research = await view.get("research_results")
            article = {
                "title": f"Article about {research['topic']}",
                "content": f"Based on research: {research['summary']}",
                "sections": ["Introduction", "Main Content", "Conclusion"]
            }
            await view.put("article_draft", article)
            return article

        async def reviewer_handler(ecm, view):
            """Reviewer agent that validates content."""
            article = await view.get("article_draft")
            review = {
                "status": "approved",
                "feedback": "Great article!",
                "score": 95,
                "article_title": article["title"]
            }
            await view.put("review_result", review)
            return review

        # 4. Create agents
        print("Creating agents...")
        await hf.create_agent(
            agent_id="researcher",
            skills={"search", "analyze", "summarize"},
            read_keys=set(),
            write_keys={"research_results"},
            task_handler=researcher_handler,
        )
        print("  [ok] Researcher created")

        await hf.create_agent(
            agent_id="writer",
            skills={"write", "edit", "format"},
            read_keys={"research_results"},
            write_keys={"article_draft"},
            task_handler=writer_handler,
        )
        print("  [ok] Writer created")

        await hf.create_agent(
            agent_id="reviewer",
            skills={"review", "validate", "fact_check"},
            read_keys={"article_draft"},
            write_keys={"review_result"},
            task_handler=reviewer_handler,
        )
        print("  [ok] Reviewer created")

        # 5. Execute workflow (sequential tasks)
        print("\nExecuting multi-agent workflow...\n")

        # Task 1: Research
        ecm1 = ECM(
            trace_id="multi-agent-1",
            intent="Research AI trends in 2025",
            intent_id="research-1",
            emitter="user",
            required_skills=["search"],
            payload={"topic": "AI Trends 2025"},
        )
        await hf.scheduler.schedule(ecm1)
        await asyncio.sleep(0.3)
        print("  [ok] Research completed")

        # Task 2: Write
        ecm2 = ECM(
            trace_id="multi-agent-1",
            intent="Write article based on research",
            intent_id="write-1",
            emitter="user",
            required_skills=["write"],
            payload={},
        )
        await hf.scheduler.schedule(ecm2)
        await asyncio.sleep(0.3)
        print("  [ok] Writing completed")

        # Task 3: Review
        ecm3 = ECM(
            trace_id="multi-agent-1",
            intent="Review and validate article",
            intent_id="review-1",
            emitter="user",
            required_skills=["review"],
            payload={},
        )
        await hf.scheduler.schedule(ecm3)
        await asyncio.sleep(0.3)
        print("  [ok] Review completed")

        # 6. Get final result
        review_result = await hf.blackboard.sys_get("review_result")
        print(f"\nMulti-agent workflow completed!")
        print(f"Final Review: {review_result}")

    finally:
        # 7. Clean shutdown
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

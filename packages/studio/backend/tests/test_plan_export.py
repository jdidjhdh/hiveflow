"""Tests for plan export utilities."""

from app.utils.plan_export import normalize_studio_plan


def test_normalize_studio_plan_hitl_and_skills():
    raw = {
        "review": {
            "depends_on": ["draft"],
            "hitl_config": {"action": "approval", "prompt": "ok?"},
            "skills": ["review"],
        },
    }
    plan = normalize_studio_plan(raw)
    assert plan["review"]["task"] == "review"
    assert plan["review"]["hitl"]["action"] == "approval"
    assert plan["review"]["depends_on"] == ["draft"]

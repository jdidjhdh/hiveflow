import pytest
from guardrails.input import InputGuard
from guardrails.output import OutputValidator


@pytest.mark.asyncio
async def test_input_blocked():
    guard = InputGuard(blocked_patterns=[r"\bdrop table\b"])
    with pytest.raises(ValueError, match="blocked"):
        await guard.check("SELECT * FROM users; DROP TABLE users;")


@pytest.mark.asyncio
async def test_input_allowed():
    guard = InputGuard(blocked_patterns=[r"\bdrop table\b"])
    result = await guard.check("What is the weather today?")
    assert result is True


@pytest.mark.asyncio
async def test_invalid_pattern():
    guard = InputGuard(blocked_patterns=["[invalid("])  # Invalid regex, falls back to literal match
    result = await guard.check("test [invalid(")
    assert result is True

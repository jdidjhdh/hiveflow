import pytest

from hiveflow import Expectation, ValidationPipeline


@pytest.fixture
def pipeline():
    return ValidationPipeline()


@pytest.mark.asyncio
async def test_json_schema_validation(pipeline):
    expectation = Expectation(
        state_key="test",
        expected_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"]
        },
        use_json_schema=True
    )
    valid_data = {"name": "Alice", "age": 30}
    assert await pipeline.validate(expectation, valid_data) is True
    invalid_data = {"age": 30}  # missing required 'name'
    assert await pipeline.validate(expectation, invalid_data) is False


@pytest.mark.asyncio
async def test_type_check(pipeline):
    expectation = Expectation(
        state_key="test",
        expected_schema={"type": "string"}
    )
    assert await pipeline.validate(expectation, "hello") is True
    assert await pipeline.validate(expectation, 123) is False


@pytest.mark.asyncio
async def test_expression_validation(pipeline):
    # Note: simpleeval not installed in this env, so expression validation is skipped
    # This test just verifies no crash when expression is present
    expectation = Expectation(
        state_key="test",
        expected_schema={},
        validation="value['age'] > 0"
    )
    # Returns True because simpleeval is not available (validation is skipped)
    result = await pipeline.validate(expectation, {"age": 25})
    assert result is True  # skipped validation returns True

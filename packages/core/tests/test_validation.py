import importlib.util

import pytest

from hiveflow import Expectation, ValidationPipeline


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


_JSONSCHEMA_AVAILABLE = _has_module("jsonschema")


@pytest.fixture
def pipeline():
    return ValidationPipeline()


@pytest.mark.asyncio
@pytest.mark.skipif(not _JSONSCHEMA_AVAILABLE, reason="jsonschema package not installed")
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
    # 安全表达式求值：AST 白名单仅允许比较/算术/逻辑运算，下标访问（Subscript）被拦截
    # 白名单支持的表达式正确求值
    expectation = Expectation(
        state_key="test",
        expected_schema={},
        validation="value > 0"
    )
    assert await pipeline.validate(expectation, 25) is True
    assert await pipeline.validate(expectation, -5) is False

    # 下标访问不在白名单，被安全拦截返回 False（而非崩溃或执行）
    expectation2 = Expectation(
        state_key="test",
        expected_schema={},
        validation="value['age'] > 0"
    )
    assert await pipeline.validate(expectation2, {"age": 25}) is False

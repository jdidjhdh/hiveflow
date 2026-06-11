import logging
from typing import Any

try:
    from . import Expectation
except ImportError:
    from hiveflow import Expectation

logger = logging.getLogger(__name__)

try:
    import jsonschema

    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

try:
    from simpleeval import simple_eval

    _SIMPLEEVAL_AVAILABLE = True
except ImportError:
    _SIMPLEEVAL_AVAILABLE = False


class ValidationPipeline:
    async def validate(self, expectation: Expectation, value: Any) -> bool:
        if expectation.use_json_schema:
            if not _JSONSCHEMA_AVAILABLE:
                raise ImportError("jsonschema is required when use_json_schema=True")
            try:
                jsonschema.validate(instance=value, schema=expectation.expected_schema)
            except Exception as e:
                logger.warning(f"JSON Schema validation failed: {e}")
                return False
        else:
            if not self._type_check(expectation.expected_schema, value):
                return False
        if expectation.validation:
            if not self._eval_expression(expectation.validation, value):
                return False
        return True

    def _type_check(self, schema: dict, value: Any) -> bool:
        expected_type = schema.get("type")
        if expected_type is None:
            return True
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }
        if expected_type in type_map:
            expected_cls = type_map[expected_type]
            if expected_type == "number" and isinstance(value, bool):
                return False
            if expected_type == "integer" and isinstance(value, bool):
                return False
            if not isinstance(value, expected_cls):
                return False
        else:
            logger.warning(f"Unknown schema type: {expected_type}, accepting.")
        return True

    def _eval_expression(self, expression: str, value: Any) -> bool:
        if _SIMPLEEVAL_AVAILABLE:
            try:
                return bool(simple_eval(expression, names={"value": value}))
            except Exception:
                return False
        else:
            logger.warning("simpleeval not installed; custom validation skipped.")
            return True

"""Validation pipeline with safe expression evaluation.

Security Enhancement:
- Removed simple_eval dependency due to code injection risk
- Implemented safe AST-based expression parser with operator whitelist
- Supports: comparisons, arithmetic, logical operators, 'value' variable only
"""

import ast
import logging
import operator
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


# 🔒 Safe operator whitelist for expression evaluation
# Only allows safe operations, no function calls, no imports, no attribute access
SAFE_OPERATORS = {
    # Comparisons
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    # Identity
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    # Arithmetic (safe for numbers)
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    # Logical
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: operator.not_,
    # Unary
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
    # Contains (for 'in' operator)
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# Allowed node types (whitelist)
ALLOWED_NODES = {
    ast.Expression,
    ast.BoolOp,      # and/or
    ast.UnaryOp,     # not, +, -
    ast.BinOp,       # +, -, *, /, %, etc.
    ast.Compare,     # ==, !=, <, >, <=, >=
    ast.Name,        # variable names (only 'value' allowed)
    ast.Constant,    # literals (numbers, strings, booleans)
    ast.Num,         # legacy Python < 3.8
    ast.Str,         # legacy Python < 3.8
    ast.Load,        # expression context (read mode)
    # Comparison operators (as children of Compare)
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    # Binary operators (as children of BinOp)
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.FloorDiv, ast.Pow, ast.LShift, ast.RShift,
    ast.BitOr, ast.BitXor, ast.BitAnd,
    # Unary operators (as children of UnaryOp)
    ast.UAdd, ast.USub, ast.Invert,
    # Boolean operators (as children of BoolOp)
    ast.And, ast.Or,
    ast.Not,         # as child of UnaryOp
}


class UnsafeExpressionError(Exception):
    """Raised when expression contains disallowed operations."""
    pass


class SafeExpressionEvaluator:
    """
    🔒 AST-based safe expression evaluator.
    
    Security guarantees:
    - No function calls allowed
    - No attribute access (obj.attr)
    - No imports (__import__)
    - No subscripts (obj[key])
    - Only 'value' variable allowed
    - Operator whitelist enforced
    
    Supported expressions:
    - value > 0
    - value == "success"
    - value >= 10 and value <= 100
    - "error" in value
    - not value
    """
    
    ALLOWED_NAMES = {"value", "True", "False", "None"}
    
    def evaluate(self, expression: str, value: Any) -> bool:
        """
        Safely evaluate expression with 'value' variable.
        
        Args:
            expression: Safe expression string (e.g., "value > 0")
            value: The value to check against
            
        Returns:
            Boolean result of expression
            
        Raises:
            UnsafeExpressionError: If expression contains disallowed syntax
            SyntaxError: If expression has invalid syntax
        """
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            logger.warning(f"Expression syntax error: {expression} - {e}")
            raise
        
        # Validate tree structure
        self._validate_tree(tree)
        
        # Evaluate
        try:
            result = self._eval_node(tree.body, value)
            return bool(result)
        except Exception as e:
            logger.warning(f"Expression evaluation failed: {expression} - {e}")
            return False
    
    def _validate_tree(self, tree: ast.AST) -> None:
        """
        Validate AST contains only allowed node types.
        
        Raises:
            UnsafeExpressionError: If disallowed node found
        """
        for node in ast.walk(tree):
            if type(node) not in ALLOWED_NODES:
                raise UnsafeExpressionError(
                    f"Disallowed syntax: {type(node).__name__}. "
                    f"Only comparisons, arithmetic, and logical operators are allowed."
                )
            
            # Check Name nodes (only 'value' allowed)
            if isinstance(node, ast.Name):
                if node.id not in self.ALLOWED_NAMES:
                    raise UnsafeExpressionError(
                        f"Disallowed variable: '{node.id}'. Only 'value' is allowed."
                    )
            
            # Check function calls (strictly forbidden)
            if isinstance(node, ast.Call):
                raise UnsafeExpressionError(
                    "Function calls are not allowed in expressions."
                )
            
            # Check attribute access (strictly forbidden)
            if isinstance(node, ast.Attribute):
                raise UnsafeExpressionError(
                    "Attribute access is not allowed in expressions."
                )
            
            # Check subscripts (strictly forbidden)
            if isinstance(node, ast.Subscript):
                raise UnsafeExpressionError(
                    "Subscript access (obj[key]) is not allowed in expressions."
                )
    
    def _eval_node(self, node: ast.AST, value: Any) -> Any:
        """
        Recursively evaluate AST node with operator whitelist.
        
        Args:
            node: AST node to evaluate
            value: The 'value' variable
            
        Returns:
            Evaluation result
        """
        # Literals (Python 3.8+)
        if isinstance(node, ast.Constant):
            return node.value
        
        # Legacy literals (Python < 3.8)
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Str):
            return node.s
        
        # Variable reference
        if isinstance(node, ast.Name):
            if node.id == "value":
                return value
            elif node.id == "True":
                return True
            elif node.id == "False":
                return False
            elif node.id == "None":
                return None
            raise UnsafeExpressionError(f"Unknown variable: {node.id}")
        
        # Binary operations (+, -, *, /, %, etc.)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, value)
            right = self._eval_node(node.right, value)
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise UnsafeExpressionError(f"Disallowed operator: {op_type.__name__}")
            return SAFE_OPERATORS[op_type](left, right)
        
        # Unary operations (not, +, -)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, value)
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise UnsafeExpressionError(f"Disallowed operator: {op_type.__name__}")
            return SAFE_OPERATORS[op_type](operand)
        
        # Boolean operations (and, or)
        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, value) for v in node.values]
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise UnsafeExpressionError(f"Disallowed operator: {op_type.__name__}")
            result = values[0]
            for v in values[1:]:
                result = SAFE_OPERATORS[op_type](result, v)
            return result
        
        # Comparisons (==, !=, <, >, <=, >=, in, not in)
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, value)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, value)
                op_type = type(op)
                if op_type not in SAFE_OPERATORS:
                    raise UnsafeExpressionError(f"Disallowed operator: {op_type.__name__}")
                if not SAFE_OPERATORS[op_type](left, right):
                    return False
                left = right  # Chain comparisons
            return True
        
        raise UnsafeExpressionError(f"Unsupported node type: {type(node).__name__}")


# Global safe evaluator instance
_safe_evaluator = SafeExpressionEvaluator()


class ValidationPipeline:
    """Validation pipeline with JSON Schema and safe expression support."""
    
    async def validate(self, expectation: Expectation, value: Any) -> bool:
        """
        Validate value against expectation.
        
        Args:
            expectation: Validation expectation with schema and/or expression
            value: Value to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        if expectation.use_json_schema:
            if not _JSONSCHEMA_AVAILABLE:
                raise ImportError("jsonschema is required when use_json_schema=True")
            try:
                jsonschema.validate(instance=value, schema=expectation.expected_schema)
            except jsonschema.ValidationError as e:
                logger.warning(f"JSON Schema validation failed: {e.message}")
                return False
            except Exception as e:
                logger.warning(f"JSON Schema validation error: {e}")
                return False
        else:
            if not self._type_check(expectation.expected_schema, value):
                return False
        
        if expectation.validation:
            if not self._eval_expression(expectation.validation, value):
                return False
        
        return True
    
    def _type_check(self, schema: dict, value: Any) -> bool:
        """
        Check value type against schema.
        
        Args:
            schema: Type schema with 'type' key
            value: Value to check
            
        Returns:
            True if type matches, False otherwise
        """
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
            # Boolean is subclass of int in Python, need explicit check
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
        """
        🔒 Safely evaluate validation expression.
        
        Security guarantees:
        - AST-based parsing with operator whitelist
        - No function calls, imports, or attribute access
        - Only 'value' variable allowed
        
        Args:
            expression: Safe expression string (e.g., "value > 0")
            value: The value to validate
            
        Returns:
            Boolean result of expression
        """
        try:
            return _safe_evaluator.evaluate(expression, value)
        except UnsafeExpressionError as e:
            logger.warning(f"Unsafe expression blocked: {expression} - {e}")
            return False
        except SyntaxError as e:
            logger.warning(f"Expression syntax error: {expression} - {e}")
            return False
        except Exception as e:
            logger.warning(f"Expression evaluation failed: {expression} - {e}")
            return False


def is_expression_safe(expression: str) -> bool:
    """
    Check if expression is safe to evaluate.
    
    Args:
        expression: Expression string to check
        
    Returns:
        True if expression passes safety check
    """
    try:
        tree = ast.parse(expression, mode='eval')
        _safe_evaluator._validate_tree(tree)
        return True
    except (UnsafeExpressionError, SyntaxError):
        return False
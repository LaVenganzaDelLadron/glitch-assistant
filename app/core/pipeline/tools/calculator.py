"""Safe arithmetic calculator tool.

Uses Python's ast.literal_eval restricted to numeric and boolean literals
with simple mathematical operators, avoiding the security risks of eval().
"""

from __future__ import annotations
import ast
import operator
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Allowed operators mapped to their safe implementations
_ALLOWED_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Regex patterns for natural language math phrase replacement
# Ordered so longer / more specific patterns are matched before shorter ones
_NL_MATH_REPLACEMENTS: list[tuple[str, str]] = [
    # Exponentials
    (r"\bto\s+the\s+power\s+of\b", "**"),
    (r"\braised\s+to\s+(?:the\s+)?\d+(?:st|nd|rd|th)?\s+power\b", "**"),
    (r"\braise\s+to\s+(?:the\s+)?\d+(?:st|nd|rd|th)?\s+power\b", "**"),
    (r"\bsquared\b", "**2"),
    (r"\bcubed\b", "**3"),
    (r"\bto\s+the\b", "**"),  # "to the 4" -> "** 4" (handled below)
    # Multiplicative
    (r"\btimes\b", "*"),
    (r"\bmultiplied\s+by\b", "*"),
    (r"\bmultiply\s+by\b", "*"),
    (r"\bproduct\s+of\b", "*"),
    # Division
    (r"\bdivided\s+by\b", "/"),
    (r"\bdivide\s+by\b", "/"),
    (r"\bover\b", "/"),
    (r"\bquotient\s+of\b", "/"),
    # Addition
    (r"\bplus\b", "+"),
    (r"\badded\s+to\b", "+"),
    (r"\badd\b", "+"),
    (r"\band\b", "+"),
    (r"\bsum\s+of\b", "+"),
    # Subtraction
    (r"\bminus\b", "-"),
    (r"\bsubtracted\s+from\b", "-"),
    (r"\bsubtract\b", "-"),
    (r"\bdifference\s+of\b", "-"),
    # Modulo
    (r"\bmod\b", "%"),
    (r"\bmodulo\b", "%"),
    (r"\bremainder\s+of\b", "%"),
]


def _preprocess_expression(text: str) -> str:
    """Convert English math phrases into Python arithmetic operators.

    Handles natural language expressions such as:
        "4 to the power of 2"      → "4 ** 2"
        "4 x 6"                    → "4 * 6"
        "4 times 6"                → "4 * 6"
        "4 plus 6 minus 2"         → "4 + 6 - 2"
        "4 squared"                → "4 ** 2"
        "4 cubed"                  → "4 ** 3"
        "4 divided by 2"           → "4 / 2"
        "4 multiplied by 8"        → "4 * 8"

    Args:
        text: Raw expression string possibly containing English math phrases.

    Returns:
        A string with natural language replaced by Python operators.
    """
    expr = text.lower().strip()

    # Apply NL phrase replacements in order
    for pattern, replacement in _NL_MATH_REPLACEMENTS:
        expr = re.sub(pattern, replacement, expr)

    # Remove common filler words that don't affect arithmetic
    filler_words = [
        r"\bthe\b",
        r"\ba\b",
        r"\ban\b",
        r"\bwhat\b",
        r"\bis\b",
        r"\bof\b",
        r"\bcompute\b",
        r"\bcalculate\b",
        r"\bcomputes\b",
        r"\bcalculates\b",
        r"\blet\b",
        r"\bme\b",
        r"\bplease\b",
        r"\bcan\b",
        r"\byou\b",
        r"\bdo\b",
        r"\bgive\b",
        r"\bget\b",
        r"\bfind\b",
        r"\bsolve\b",
        r"\bevaluate\b",
        r"\bfigure\b",
        r"\bout\b",
        r"\bresult\b",
        r"\banswer\b",
    ]
    for filler in filler_words:
        expr = re.sub(filler, "", expr)

    # Replace 'x' used as multiplication sign between numbers (e.g. "4 x 6")
    expr = re.sub(r"(\d)\s*[xX×]\s*(\d)", r"\1 * \2", expr)

    # Clean up extra whitespace and stray operators
    expr = re.sub(r"\s+", " ", expr).strip()

    # Remove leading/trailing operators
    expr = re.sub(r"^[\+\-\*\/%\*\*]+", "", expr)
    expr = re.sub(r"[\+\-\*\/%\*\*]+$", "", expr)

    return expr.strip()


def _safe_eval(node: ast.AST) -> Any:
    """Recursively evaluate an AST node using only allowed operations.

    Args:
        node: An AST node to evaluate.

    Returns:
        The numeric result of evaluating the node.

    Raises:
        ValueError: If the node uses disallowed syntax.
        ZeroDivisionError: If a division by zero occurs.
    """
    if isinstance(node, ast.Constant):
        # Only allow numbers (int, float, complex) and booleans
        if isinstance(node.value, (int, float, complex, bool)):
            return node.value
        raise ValueError(f"Literal {node.value!r} is not allowed.")

    if isinstance(node, ast.UnaryOp):
        op_func = _ALLOWED_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unary operator {type(node.op).__name__} is not allowed.")
        operand = _safe_eval(node.operand)
        return op_func(operand)

    if isinstance(node, ast.BinOp):
        op_func = _ALLOWED_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Binary operator {type(node.op).__name__} is not allowed.")
        left = _safe_eval(node.operand)
        right = _safe_eval(node.right)
        return op_func(left, right)

    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    raise ValueError(f"Syntax {type(node).__name__} is not allowed.")


def execute(text: str) -> str | None:
    """Evaluate a simple arithmetic expression from text.

    Accepts expressions in natural language (e.g. "calculate 4 to the power
    of 2", "what is 4 x 6", "4 times 8 plus 2") alongside standard Python
    arithmetic operators (+, -, *, /, //, **, %).  Variable assignment,
    function calls, and attribute access are **not** allowed.

    Args:
        text: User input containing a phrase like "calculate …".

    Returns:
        A formatted string with the answer, or an error message if parsing
        fails.
    """
    # Extract the expression part — "calculate" may appear anywhere in the text
    expr = text.lower()
    for trigger in ("calculate", "compute", "evaluate", "what is", "what's"):
        if trigger in expr:
            parts = expr.split(trigger, 1)
            expr = parts[1] if len(parts) > 1 else expr
            break

    expression = expr.strip()
    if not expression:
        return "Please provide an expression to evaluate."

    # Preprocess natural language to Python operators
    expression = _preprocess_expression(expression)

    # Guard against empty expression after preprocessing
    if not expression:
        return "Please provide a valid numeric expression."

    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        answer = f"ANSWER: {result}"
        logger.info(answer)
        return answer
    except ZeroDivisionError:
        msg = "ERROR: Division by zero."
        logger.warning(msg)
        return msg
    except (ValueError, SyntaxError, TypeError) as exc:
        msg = f"ERROR: Invalid expression — {exc}"
        logger.warning(msg)
        return msg

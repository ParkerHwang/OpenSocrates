"""Hand-written Decimal calculation parser, evaluator, and verifier.

The expression language is intentionally tiny: decimal literals, named
operands, parentheses, unary minus, ``+ - * /``, and postfix percentage
conversion.  It has no dynamic language escape hatch.  Every token and AST
node is bounded before evaluation, and every arithmetic operation is performed
with :class:`decimal.Decimal` under a fixed finite context.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    localcontext,
)
from enum import StrEnum
from typing import Any, NoReturn

from ..domain.enums import RoundingMode, ViolationSeverity
from ..domain.models import Calculation, SourceReference, Violation
from ..errors import ValidationError

MAX_EXPRESSION_TOKENS = 128
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 32
MAX_CALCULATION_OPERANDS = 64
MAX_DECIMAL_PRECISION = 256
MAX_UNIT_TERMS = 32

# Expression literals are unsigned and use unary ``-`` for negation, while
# S01's DecimalString fields legitimately carry a leading minus.  Keep those
# two boundaries explicit: this regex is only for model operand/result text.
_DECIMAL_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_IDENTIFIER_START_RE = re.compile(r"[A-Za-z_]")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_UNIT_TERM_RE = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9_]*|1)(?:\^(?P<power>[1-9][0-9]*))?\Z")


class CalculationFailureCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    EMPTY_EXPRESSION = "empty_expression"
    INVALID_TOKEN = "invalid_token"
    UNSUPPORTED_SYNTAX = "unsupported_syntax"
    UNEXPECTED_TOKEN = "unexpected_token"
    UNKNOWN_OPERAND = "unknown_operand"
    DUPLICATE_OPERAND = "duplicate_operand"
    UNUSED_OPERAND = "unused_operand"
    TOO_COMPLEX = "too_complex"
    TOO_DEEP = "too_deep"
    INVALID_DECIMAL = "invalid_decimal"
    NON_FINITE = "non_finite"
    DIVISION_BY_ZERO = "division_by_zero"
    UNIT_INVALID = "unit_invalid"
    UNIT_MISMATCH = "unit_mismatch"
    RESULT_MISMATCH = "result_mismatch"
    INVALID_ROUNDING = "invalid_rounding"
    PROVENANCE_MISSING = "provenance_missing"
    PROVENANCE_UNKNOWN = "provenance_unknown"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class CalculationFailure:
    """One stable calculation failure without echoing input values."""

    code: CalculationFailureCode
    message: str
    position: int | None = None


class CalculationError(ValidationError):
    """Raised by direct parser/evaluator APIs for a specific failure."""

    def __init__(self, failure: CalculationFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure
        self.failure_code = failure.code


@dataclass(frozen=True, slots=True)
class CalculationVerification:
    """Bounded result of deterministic calculation verification."""

    value: Decimal | None = None
    expected: Decimal | None = None
    unit: str | None = None
    derived_unit: str | None = None
    provenance: tuple[str, ...] = ()
    failures: tuple[CalculationFailure, ...] = ()
    expression_tree: "ExpressionNode | None" = None
    tokens: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether verification completed without any failure."""

        return not self.failures

    @property
    def passed(self) -> bool:
        """Readable alias for :attr:`ok`."""

        return self.ok

    @property
    def failure_codes(self) -> tuple[CalculationFailureCode, ...]:
        return tuple(item.code for item in self.failures)


class TokenKind(StrEnum):
    NUMBER = "number"
    NAME = "name"
    SYMBOL = "symbol"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    position: int


class ExpressionNode:
    """Marker base class for the local, non-executable expression tree."""


@dataclass(frozen=True, slots=True)
class LiteralNode(ExpressionNode):
    value: Decimal


@dataclass(frozen=True, slots=True)
class OperandNode(ExpressionNode):
    name: str


@dataclass(frozen=True, slots=True)
class UnaryMinusNode(ExpressionNode):
    child: ExpressionNode


@dataclass(frozen=True, slots=True)
class PercentNode(ExpressionNode):
    child: ExpressionNode


@dataclass(frozen=True, slots=True)
class BinaryNode(ExpressionNode):
    operator: str
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True, slots=True)
class UnitSignature:
    terms: tuple[tuple[str, int], ...] = ()


def _failure(
    code: CalculationFailureCode,
    message: str,
    position: int | None = None,
) -> CalculationError:
    return CalculationError(CalculationFailure(code=code, message=message, position=position))


def _raise_failure(
    code: CalculationFailureCode, message: str, position: int | None = None
) -> NoReturn:
    raise _failure(code, message, position)


def tokenize_expression(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    expression: str,
    *,
    max_tokens: int = MAX_EXPRESSION_TOKENS,
) -> tuple[Token, ...]:
    """Tokenize only the closed arithmetic grammar."""

    if not isinstance(expression, str):
        _raise_failure(CalculationFailureCode.INVALID_INPUT, "expression must be text")
    if not expression.strip(" \t\r\n"):
        _raise_failure(CalculationFailureCode.EMPTY_EXPRESSION, "expression is empty")
    tokens: list[Token] = []
    position = 0
    while position < len(expression):
        character = expression[position]
        if character in " \t\r\n":
            position += 1
            continue
        if character.isascii() and character.isdigit():
            start = position
            while (
                position < len(expression)
                and expression[position].isascii()
                and expression[position].isdigit()
            ):
                position += 1
            if position < len(expression) and expression[position] == ".":
                position += 1
                fraction_start = position
                while (
                    position < len(expression)
                    and expression[position].isascii()
                    and expression[position].isdigit()
                ):
                    position += 1
                if fraction_start == position:
                    _raise_failure(
                        CalculationFailureCode.INVALID_TOKEN, "decimal literal is malformed", start
                    )
            raw = expression[start:position]
            if raw.startswith("0") and len(raw) > 1 and raw[1].isdigit():
                _raise_failure(
                    CalculationFailureCode.INVALID_TOKEN,
                    "decimal literal has a leading zero",
                    start,
                )
            if len(tokens) >= max_tokens:
                _raise_failure(
                    CalculationFailureCode.TOO_COMPLEX, "expression token limit exceeded", start
                )
            tokens.append(Token(TokenKind.NUMBER, raw, start))
            continue
        if _IDENTIFIER_START_RE.fullmatch(character):
            start = position
            position += 1
            while position < len(expression):
                candidate = expression[position]
                if not (candidate.isascii() and (candidate.isalnum() or candidate == "_")):
                    break
                position += 1
            name = expression[start:position]
            if _IDENTIFIER_RE.fullmatch(name) is None:
                _raise_failure(
                    CalculationFailureCode.INVALID_TOKEN, "operand name is malformed", start
                )
            if len(tokens) >= max_tokens:
                _raise_failure(
                    CalculationFailureCode.TOO_COMPLEX, "expression token limit exceeded", start
                )
            tokens.append(Token(TokenKind.NAME, name, start))
            continue
        if character in "()+-*/%":
            if len(tokens) >= max_tokens:
                _raise_failure(
                    CalculationFailureCode.TOO_COMPLEX, "expression token limit exceeded", position
                )
            tokens.append(Token(TokenKind.SYMBOL, character, position))
            position += 1
            continue
        _raise_failure(
            CalculationFailureCode.INVALID_TOKEN,
            "expression contains an unsupported token",
            position,
        )
    return tuple(tokens)


class _ExpressionParser:
    def __init__(
        self,
        tokens: tuple[Token, ...],
        *,
        max_nodes: int,
        max_depth: int,
    ) -> None:
        self.tokens = tokens
        self.index = 0
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.node_count = 0

    def _current(self) -> Token | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def _consume(self, expected: str | None = None) -> Token:
        token = self._current()
        if token is None:
            _raise_failure(CalculationFailureCode.UNEXPECTED_TOKEN, "expression ends unexpectedly")
        if expected is not None and token.text != expected:
            _raise_failure(
                CalculationFailureCode.UNEXPECTED_TOKEN,
                "expression token is in the wrong position",
                token.position,
            )
        self.index += 1
        return token

    def _node(self, node: ExpressionNode) -> ExpressionNode:
        self.node_count += 1
        if self.node_count > self.max_nodes:
            _raise_failure(CalculationFailureCode.TOO_COMPLEX, "expression node limit exceeded")
        return node

    def _check_depth(self, depth: int) -> None:
        if depth > self.max_depth:
            _raise_failure(CalculationFailureCode.TOO_DEEP, "expression nesting limit exceeded")

    def parse(self) -> ExpressionNode:
        if not self.tokens:
            _raise_failure(CalculationFailureCode.EMPTY_EXPRESSION, "expression is empty")
        result = self._parse_sum(0)
        trailing = self._current()
        if trailing is not None:
            _raise_failure(
                CalculationFailureCode.UNEXPECTED_TOKEN,
                "expression has trailing tokens",
                trailing.position,
            )
        return result

    def _parse_sum(self, depth: int) -> ExpressionNode:
        self._check_depth(depth)
        result = self._parse_product(depth)
        while (token := self._current()) is not None and token.text in {"+", "-"}:
            operator = self._consume().text
            right = self._parse_product(depth)
            result = self._node(BinaryNode(operator, result, right))
        return result

    def _parse_product(self, depth: int) -> ExpressionNode:
        self._check_depth(depth)
        result = self._parse_unary(depth)
        while (token := self._current()) is not None and token.text in {"*", "/"}:
            operator = self._consume().text
            right = self._parse_unary(depth)
            result = self._node(BinaryNode(operator, result, right))
        return result

    def _parse_unary(self, depth: int) -> ExpressionNode:
        self._check_depth(depth)
        token = self._current()
        if token is not None and token.text == "-":
            self._consume("-")
            result = self._node(UnaryMinusNode(self._parse_unary(depth + 1)))
        elif token is not None and token.text == "+":
            _raise_failure(
                CalculationFailureCode.UNSUPPORTED_SYNTAX,
                "unary plus is not allowed",
                token.position,
            )
        else:
            result = self._parse_primary(depth)
        # Percentage is postfix and converts a unitless quantity to a fraction.
        if (percent := self._current()) is not None and percent.text == "%":
            self._consume("%")
            result = self._node(PercentNode(result))
            if (repeat := self._current()) is not None and repeat.text == "%":
                _raise_failure(
                    CalculationFailureCode.UNSUPPORTED_SYNTAX,
                    "repeated percentage conversion is not allowed",
                    repeat.position,
                )
        return result

    def _parse_primary(self, depth: int) -> ExpressionNode:
        self._check_depth(depth)
        token = self._current()
        if token is None:
            _raise_failure(CalculationFailureCode.UNEXPECTED_TOKEN, "expression is incomplete")
        if token.kind is TokenKind.NUMBER:
            self._consume()
            try:
                value = Decimal(token.text)
            except DecimalException as exc:
                raise _failure(
                    CalculationFailureCode.INVALID_DECIMAL,
                    "decimal literal is invalid",
                    token.position,
                ) from exc
            if not value.is_finite():
                _raise_failure(
                    CalculationFailureCode.NON_FINITE,
                    "decimal literal is non-finite",
                    token.position,
                )
            return self._node(LiteralNode(value))
        if token.kind is TokenKind.NAME:
            self._consume()
            return self._node(OperandNode(token.text))
        if token.text == "(":
            self._consume("(")
            result = self._parse_sum(depth + 1)
            self._consume(")")
            return result
        _raise_failure(
            CalculationFailureCode.UNSUPPORTED_SYNTAX,
            "expression token is not supported",
            token.position,
        )


def parse_expression(
    expression: str,
    *,
    max_tokens: int = MAX_EXPRESSION_TOKENS,
    max_nodes: int = MAX_EXPRESSION_NODES,
    max_depth: int = MAX_EXPRESSION_DEPTH,
) -> ExpressionNode:
    """Parse the bounded expression grammar into a local AST."""

    tokens = tokenize_expression(expression, max_tokens=max_tokens)
    return _ExpressionParser(tokens, max_nodes=max_nodes, max_depth=max_depth).parse()


def _operand_names(node: ExpressionNode) -> tuple[str, ...]:
    found: list[str] = []

    def visit(item: ExpressionNode) -> None:
        if isinstance(item, OperandNode):
            found.append(item.name)
        elif isinstance(item, (UnaryMinusNode, PercentNode)):
            visit(item.child)
        elif isinstance(item, BinaryNode):
            visit(item.left)
            visit(item.right)

    visit(node)
    return tuple(found)


def _coerce_decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and _DECIMAL_RE.fullmatch(value):
        try:
            result = Decimal(value)
        except DecimalException as exc:
            raise _failure(CalculationFailureCode.INVALID_DECIMAL, f"{field} is invalid") from exc
    elif isinstance(value, int) and not isinstance(value, bool):
        result = Decimal(value)
    else:
        raise _failure(CalculationFailureCode.INVALID_DECIMAL, f"{field} is invalid")
    if not result.is_finite():
        _raise_failure(CalculationFailureCode.NON_FINITE, f"{field} is non-finite")
    return result


def _evaluate_node(node: ExpressionNode, values: Mapping[str, Decimal]) -> Decimal:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, OperandNode):
        if node.name not in values:
            _raise_failure(
                CalculationFailureCode.UNKNOWN_OPERAND, "expression references an unknown operand"
            )
        return values[node.name]
    if isinstance(node, UnaryMinusNode):
        result = -_evaluate_node(node.child, values)
    elif isinstance(node, PercentNode):
        result = _evaluate_node(node.child, values) / Decimal(100)
    elif isinstance(node, BinaryNode):
        left = _evaluate_node(node.left, values)
        right = _evaluate_node(node.right, values)
        if node.operator == "+":
            result = left + right
        elif node.operator == "-":
            result = left - right
        elif node.operator == "*":
            result = left * right
        elif node.operator == "/":
            if right == 0:
                _raise_failure(
                    CalculationFailureCode.DIVISION_BY_ZERO, "expression divides by zero"
                )
            try:
                result = left / right
            except (DivisionByZero, InvalidOperation) as exc:
                raise _failure(
                    CalculationFailureCode.DIVISION_BY_ZERO, "expression divides by zero"
                ) from exc
        else:  # pragma: no cover - AST nodes are only constructed by the parser
            _raise_failure(CalculationFailureCode.UNSUPPORTED_SYNTAX, "unknown arithmetic operator")
    else:  # pragma: no cover - defensive closed-tree boundary
        _raise_failure(CalculationFailureCode.INVALID_INPUT, "expression tree is invalid")
    if not result.is_finite():
        _raise_failure(CalculationFailureCode.NON_FINITE, "calculation produced a non-finite value")
    return result


def evaluate_expression(
    expression: str,
    operands: Mapping[str, Any],
    *,
    max_tokens: int = MAX_EXPRESSION_TOKENS,
    max_nodes: int = MAX_EXPRESSION_NODES,
    max_depth: int = MAX_EXPRESSION_DEPTH,
) -> Decimal:
    """Evaluate one expression with Decimal values and no dynamic execution."""

    if not isinstance(operands, Mapping):
        _raise_failure(CalculationFailureCode.INVALID_INPUT, "operands must be an object")
    values: dict[str, Decimal] = {}
    for name, value in operands.items():
        if not isinstance(name, str) or _IDENTIFIER_RE.fullmatch(name) is None:
            _raise_failure(CalculationFailureCode.INVALID_INPUT, "operand name is invalid")
        if name in values:
            _raise_failure(CalculationFailureCode.DUPLICATE_OPERAND, "operand names must be unique")
        values[name] = _coerce_decimal(value, field="operand")
    tree = parse_expression(
        expression, max_tokens=max_tokens, max_nodes=max_nodes, max_depth=max_depth
    )
    names = _operand_names(tree)
    if any(name not in values for name in names):
        _raise_failure(
            CalculationFailureCode.UNKNOWN_OPERAND, "expression references an unknown operand"
        )
    with localcontext() as context:
        context.prec = MAX_DECIMAL_PRECISION
        result = _evaluate_node(tree, values)
    if not result.is_finite():
        _raise_failure(CalculationFailureCode.NON_FINITE, "calculation produced a non-finite value")
    return result


def _parse_unit(unit: Any) -> UnitSignature:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if not isinstance(unit, str) or not unit or any(character.isspace() for character in unit):
        raise _failure(CalculationFailureCode.UNIT_INVALID, "unit is not a non-empty token")
    parts = re.split(r"([*/])", unit)
    if not parts or not parts[0]:
        raise _failure(CalculationFailureCode.UNIT_INVALID, "unit expression is malformed")
    terms: dict[str, int] = {}
    sign = 1
    expecting_term = True
    for part in parts:
        if part == "*":
            if expecting_term:
                raise _failure(
                    CalculationFailureCode.UNIT_INVALID, "unit multiplication is malformed"
                )
            sign = 1
            expecting_term = True
            continue
        if part == "/":
            if expecting_term:
                raise _failure(CalculationFailureCode.UNIT_INVALID, "unit division is malformed")
            sign = -1
            expecting_term = True
            continue
        match = _UNIT_TERM_RE.fullmatch(part)
        if match is None or not expecting_term:
            raise _failure(
                CalculationFailureCode.UNIT_INVALID, "unit contains an unsupported token"
            )
        name = match.group("name")
        if name != "1":
            power = int(match.group("power") or "1") * sign
            terms[name] = terms.get(name, 0) + power
        expecting_term = False
    if expecting_term:
        raise _failure(CalculationFailureCode.UNIT_INVALID, "unit expression is incomplete")
    if len(terms) > MAX_UNIT_TERMS:
        raise _failure(CalculationFailureCode.TOO_COMPLEX, "unit term limit exceeded")
    return UnitSignature(tuple(sorted((name, power) for name, power in terms.items() if power)))


def _combine_units(left: UnitSignature, right: UnitSignature, sign: int) -> UnitSignature:
    result = dict(left.terms)
    for name, power in right.terms:
        result[name] = result.get(name, 0) + sign * power
        if result[name] == 0:
            del result[name]
    if len(result) > MAX_UNIT_TERMS:
        raise _failure(CalculationFailureCode.TOO_COMPLEX, "unit term limit exceeded")
    return UnitSignature(tuple(sorted(result.items())))


def _format_unit(unit: UnitSignature) -> str:
    if not unit.terms:
        return "1"
    numerator: list[str] = []
    denominator: list[str] = []
    for name, power in unit.terms:
        target = numerator if power > 0 else denominator
        text = name if abs(power) == 1 else f"{name}^{abs(power)}"
        target.append(text)
    top = "*".join(numerator) if numerator else "1"
    if denominator:
        return f"{top}/{'*'.join(denominator)}"
    return top


def _unit_for_node(node: ExpressionNode, units: Mapping[str, UnitSignature]) -> UnitSignature:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if isinstance(node, LiteralNode):
        return UnitSignature()
    if isinstance(node, OperandNode):
        if node.name not in units:
            _raise_failure(
                CalculationFailureCode.UNKNOWN_OPERAND, "expression references an unknown operand"
            )
        return units[node.name]
    if isinstance(node, UnaryMinusNode):
        return _unit_for_node(node.child, units)
    if isinstance(node, PercentNode):
        child = _unit_for_node(node.child, units)
        if child.terms:
            _raise_failure(
                CalculationFailureCode.UNIT_MISMATCH,
                "percentage conversion requires a unitless value",
            )
        return UnitSignature()
    if isinstance(node, BinaryNode):
        left = _unit_for_node(node.left, units)
        right = _unit_for_node(node.right, units)
        if node.operator in {"+", "-"}:
            if left != right:
                _raise_failure(
                    CalculationFailureCode.UNIT_MISMATCH,
                    "addition and subtraction require matching units",
                )
            return left
        if node.operator == "*":
            return _combine_units(left, right, 1)
        if node.operator == "/":
            return _combine_units(left, right, -1)
    _raise_failure(CalculationFailureCode.UNIT_INVALID, "expression unit tree is invalid")


def round_decimal(value: Decimal, rounding: RoundingMode | str) -> Decimal:
    """Apply one of the six closed rounding policies exactly."""

    if not isinstance(value, Decimal) or not value.is_finite():
        _raise_failure(CalculationFailureCode.NON_FINITE, "value to round is non-finite")
    if not isinstance(rounding, RoundingMode):
        try:
            rounding = RoundingMode(rounding)
        except (TypeError, ValueError) as exc:
            raise _failure(
                CalculationFailureCode.INVALID_ROUNDING, "rounding mode is unknown"
            ) from exc
    if rounding is RoundingMode.NONE:
        return value
    with localcontext() as context:
        context.prec = MAX_DECIMAL_PRECISION
        if rounding is RoundingMode.HALF_EVEN_0:
            return value.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
        if rounding is RoundingMode.HALF_EVEN_1:
            return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
        if rounding is RoundingMode.HALF_EVEN_2:
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        if rounding is RoundingMode.FLOOR:
            return value.to_integral_value(rounding=ROUND_FLOOR)
        if rounding is RoundingMode.CEILING:
            return value.to_integral_value(rounding=ROUND_CEILING)
    _raise_failure(CalculationFailureCode.INVALID_ROUNDING, "rounding mode is unknown")


def _source_map(
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None,
) -> dict[str, SourceReference] | None:
    if sources is None:
        return None
    if isinstance(sources, Mapping):
        return {str(key): value for key, value in sources.items()}
    return {str(source.source_id): source for source in sources}


def _invalid_result(failure: CalculationFailure) -> CalculationVerification:
    return CalculationVerification(failures=(failure,))


def verify_calculation(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    calculation: Calculation,
    *,
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None = None,
    required_source_ids: Iterable[str] | None = None,
    require_provenance: bool = True,
    max_tokens: int = MAX_EXPRESSION_TOKENS,
    max_nodes: int = MAX_EXPRESSION_NODES,
    max_depth: int = MAX_EXPRESSION_DEPTH,
) -> CalculationVerification:
    """Recompute and verify a typed calculation, failing closed on all errors."""

    if not isinstance(calculation, Calculation):
        return _invalid_result(
            CalculationFailure(
                CalculationFailureCode.INVALID_INPUT, "calculation must be a Calculation"
            )
        )
    try:
        operands = tuple(calculation.operands)
        if len(operands) > MAX_CALCULATION_OPERANDS:
            _raise_failure(CalculationFailureCode.TOO_COMPLEX, "calculation operand limit exceeded")
        names = [str(operand.name) for operand in operands]
        if len(set(names)) != len(names):
            _raise_failure(CalculationFailureCode.DUPLICATE_OPERAND, "operand names must be unique")
        values = {
            str(operand.name): _coerce_decimal(operand.value, field="operand")
            for operand in operands
        }
        unit_map = {str(operand.name): _parse_unit(operand.unit) for operand in operands}
        tree = parse_expression(
            calculation.expression,
            max_tokens=max_tokens,
            max_nodes=max_nodes,
            max_depth=max_depth,
        )
        used_names = _operand_names(tree)
        used_set = set(used_names)
        unknown = [name for name in used_set if name not in values]
        if unknown:
            _raise_failure(
                CalculationFailureCode.UNKNOWN_OPERAND, "expression references an unknown operand"
            )
        if any(name not in used_set for name in names):
            _raise_failure(
                CalculationFailureCode.UNUSED_OPERAND, "calculation contains an unused operand"
            )
        source_lookup = _source_map(sources)
        required = (
            None if required_source_ids is None else {str(item) for item in required_source_ids}
        )
        provenance: set[str] = set()
        for operand in operands:
            source_id = operand.source_id
            if source_id is None:
                if require_provenance:
                    _raise_failure(
                        CalculationFailureCode.PROVENANCE_MISSING,
                        "calculation operand provenance is missing",
                    )
                continue
            source_key = str(source_id)
            provenance.add(source_key)
            if source_lookup is not None:
                source = source_lookup.get(source_key)
                if not isinstance(source, SourceReference):
                    _raise_failure(
                        CalculationFailureCode.PROVENANCE_UNKNOWN,
                        "calculation operand source is unknown",
                    )
            if required is not None and source_key not in required:
                _raise_failure(
                    CalculationFailureCode.PROVENANCE_UNKNOWN,
                    "calculation operand source is outside the required provenance",
                )

        with localcontext() as context:
            context.prec = MAX_DECIMAL_PRECISION
            value = _evaluate_node(tree, values)
            derived_signature = _unit_for_node(tree, unit_map)
        derived_unit = _format_unit(derived_signature)
        declared_signature = _parse_unit(calculation.unit)
        if declared_signature != derived_signature:
            _raise_failure(
                CalculationFailureCode.UNIT_MISMATCH,
                "declared result unit does not match the expression",
            )
        expected = _coerce_decimal(calculation.result, field="result")
        rounded = round_decimal(value, calculation.rounding)
        if rounded != expected:
            _raise_failure(
                CalculationFailureCode.RESULT_MISMATCH,
                "declared result does not match recomputation",
            )
        return CalculationVerification(
            value=rounded,
            expected=expected,
            unit=str(calculation.unit),
            derived_unit=derived_unit,
            provenance=tuple(sorted(provenance)),
            expression_tree=tree,
            tokens=tuple(
                token.text
                for token in tokenize_expression(calculation.expression, max_tokens=max_tokens)
            ),
        )
    except CalculationError as exc:
        return CalculationVerification(failures=(exc.failure,))
    except Exception:
        # A verifier exception is a failed verification, never an implicit pass.
        return _invalid_result(
            CalculationFailure(
                CalculationFailureCode.INTERNAL_ERROR, "calculation verifier failed safely"
            )
        )


_CALC_RULE_IDS: dict[CalculationFailureCode, str] = {
    CalculationFailureCode.INVALID_INPUT: "OSV-CALC-001",
    CalculationFailureCode.EMPTY_EXPRESSION: "OSV-CALC-002",
    CalculationFailureCode.INVALID_TOKEN: "OSV-CALC-003",
    CalculationFailureCode.UNSUPPORTED_SYNTAX: "OSV-CALC-004",
    CalculationFailureCode.UNEXPECTED_TOKEN: "OSV-CALC-005",
    CalculationFailureCode.UNKNOWN_OPERAND: "OSV-CALC-006",
    CalculationFailureCode.DUPLICATE_OPERAND: "OSV-CALC-007",
    CalculationFailureCode.UNUSED_OPERAND: "OSV-CALC-008",
    CalculationFailureCode.TOO_COMPLEX: "OSV-CALC-009",
    CalculationFailureCode.TOO_DEEP: "OSV-CALC-010",
    CalculationFailureCode.INVALID_DECIMAL: "OSV-CALC-011",
    CalculationFailureCode.NON_FINITE: "OSV-CALC-012",
    CalculationFailureCode.DIVISION_BY_ZERO: "OSV-CALC-013",
    CalculationFailureCode.UNIT_INVALID: "OSV-CALC-014",
    CalculationFailureCode.UNIT_MISMATCH: "OSV-CALC-015",
    CalculationFailureCode.RESULT_MISMATCH: "OSV-CALC-016",
    CalculationFailureCode.INVALID_ROUNDING: "OSV-CALC-017",
    CalculationFailureCode.PROVENANCE_MISSING: "OSV-CALC-018",
    CalculationFailureCode.PROVENANCE_UNKNOWN: "OSV-CALC-019",
    CalculationFailureCode.INTERNAL_ERROR: "OSV-CALC-020",
}


def calculation_violations(
    calculation: Calculation,
    **kwargs: Any,
) -> tuple[Violation, ...]:
    """Map a calculation result to the repository's stable violation model."""

    result = verify_calculation(calculation, **kwargs)
    violations: list[Violation] = []
    for failure in result.failures:
        violations.append(
            Violation(
                rule_id=_CALC_RULE_IDS.get(failure.code, "OSV-CALC-020"),
                severity=ViolationSeverity.ERROR,
                message_key=f"calculation.{failure.code.value}",
                field="calculation",
                repair_hint_key="calculation.repair",
            )
        )
    return tuple(violations[:32])


def validate_calculation(calculation: Calculation, **kwargs: Any) -> tuple[Violation, ...]:
    """Alias for :func:`calculation_violations`."""

    return calculation_violations(calculation, **kwargs)


def enforce_calculation(calculation: Calculation, **kwargs: Any) -> CalculationVerification:
    """Raise a stable validation error unless calculation verification passes."""

    result = verify_calculation(calculation, **kwargs)
    if not result.ok:
        code = result.failures[0].code.value if result.failures else "internal_error"
        raise ValidationError(f"calculation verification failed: {code}")
    return result


def recompute_calculation(calculation: Calculation, **kwargs: Any) -> Decimal:
    """Return the verified rounded result, never a best-effort value."""

    result = verify_calculation(calculation, **kwargs)
    if not result.ok or result.value is None:
        failure = (
            result.failures[0]
            if result.failures
            else CalculationFailure(
                CalculationFailureCode.INTERNAL_ERROR, "calculation verifier failed safely"
            )
        )
        raise CalculationError(failure)
    return result.value


# Concise aliases for adapters and walkthroughs.
check_calculation = calculation_violations
verify = verify_calculation
parse_calculation_expression = parse_expression
evaluate_calculation = evaluate_expression
validate_calculation_rules = calculation_violations


__all__ = [
    "MAX_CALCULATION_OPERANDS",
    "MAX_DECIMAL_PRECISION",
    "MAX_EXPRESSION_DEPTH",
    "MAX_EXPRESSION_NODES",
    "MAX_EXPRESSION_TOKENS",
    "CalculationError",
    "CalculationFailure",
    "CalculationFailureCode",
    "CalculationVerification",
    "BinaryNode",
    "ExpressionNode",
    "LiteralNode",
    "OperandNode",
    "PercentNode",
    "Token",
    "TokenKind",
    "UnaryMinusNode",
    "UnitSignature",
    "calculation_violations",
    "check_calculation",
    "evaluate_calculation",
    "enforce_calculation",
    "evaluate_expression",
    "parse_expression",
    "parse_calculation_expression",
    "recompute_calculation",
    "round_decimal",
    "tokenize_expression",
    "validate_calculation",
    "validate_calculation_rules",
    "verify",
    "verify_calculation",
]

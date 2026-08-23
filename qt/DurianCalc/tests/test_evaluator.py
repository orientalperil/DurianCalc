"""Ported case-for-case from the macOS ExpressionEvaluatorTests.swift, plus
extra cases for the Swift/Python numeric differences described in
PORTING.md section 3 (mod sign convention, round() half-to-even, pow()
overflow/domain behaviour, malformed numbers).
"""

import math

import pytest

from duriancalc.evaluator import (
    DivisionByZeroError,
    DomainError,
    EvalError,
    ExpressionEvaluator,
    MalformedNumberError,
    UnexpectedEndError,
    UnknownIdentifierError,
)


@pytest.fixture
def evaluator() -> ExpressionEvaluator:
    return ExpressionEvaluator()


def assert_eval(evaluator: ExpressionEvaluator, expr: str, expected: float, accuracy: float = 1e-9) -> None:
    got = evaluator.evaluate(expr)
    assert got == pytest.approx(expected, abs=accuracy), expr


def assert_throws(evaluator: ExpressionEvaluator, expr: str) -> None:
    with pytest.raises(EvalError):
        evaluator.evaluate(expr)


# --- Basic arithmetic --------------------------------------------------


def test_basic_arithmetic(evaluator):
    assert_eval(evaluator, "1+2", 3)
    assert_eval(evaluator, "10-4", 6)
    assert_eval(evaluator, "6*7", 42)
    assert_eval(evaluator, "20/5", 4)
    assert_eval(evaluator, "2.5+2.5", 5)


# --- Precedence & parentheses --------------------------------------------


def test_precedence_and_parentheses(evaluator):
    assert_eval(evaluator, "2+3*4", 14)
    assert_eval(evaluator, "(2+3)*4", 20)
    assert_eval(evaluator, "2+3*4-6/2", 11)
    assert_eval(evaluator, "((10^2-10)/9)", 10)


# --- Unary operators ------------------------------------------------------


def test_unary_operators(evaluator):
    assert_eval(evaluator, "-5", -5)
    assert_eval(evaluator, "-(3+2)", -5)
    assert_eval(evaluator, "3--2", 5)  # 3 - (-2)
    assert_eval(evaluator, "+-+7", -7)


# --- Exponentiation (right-associative; unary binds looser than ^) --------


def test_exponentiation(evaluator):
    assert_eval(evaluator, "2^3", 8)
    assert_eval(evaluator, "2^3^2", 512)  # 2^(3^2), not (2^3)^2 = 64
    assert_eval(evaluator, "-2^2", -4)  # -(2^2), standard convention
    assert_eval(evaluator, "2^-1", 0.5)


# --- mod --------------------------------------------------------------------


def test_modulo(evaluator):
    assert_eval(evaluator, "10 mod 3", 1)
    assert_eval(evaluator, "10 mod 2", 0)


def test_modulo_sign_follows_dividend(evaluator):
    """Swift's truncatingRemainder(dividingBy:) is C fmod: sign follows the
    dividend, not the divisor as Python's `%` does. See PORTING.md 3.1.
    """
    assert_eval(evaluator, "-10 mod 3", -1)
    assert_eval(evaluator, "10 mod -3", 1)


# --- Constants ------------------------------------------------------------


def test_constants(evaluator):
    assert_eval(evaluator, "pi", math.pi)
    assert_eval(evaluator, "2*pi", 2 * math.pi)
    assert_eval(evaluator, "tau", 2 * math.pi)


# --- Functions --------------------------------------------------------------


def test_functions(evaluator):
    assert_eval(evaluator, "sqrt(9)", 3)
    assert_eval(evaluator, "abs(-4)", 4)
    assert_eval(evaluator, "floor(3.7)", 3)
    assert_eval(evaluator, "ceil(3.2)", 4)
    assert_eval(evaluator, "round(2.5)", 3)
    assert_eval(evaluator, "ln(e)", 1)
    assert_eval(evaluator, "log(1000)", 3)
    assert_eval(evaluator, "log2(8)", 3)
    assert_eval(evaluator, "sin(0)", 0)
    assert_eval(evaluator, "cos(0)", 1)


def test_log10_alias(evaluator):
    assert_eval(evaluator, "log10(1000)", 3)


def test_round_half_away_from_zero(evaluator):
    """Python's builtin round() rounds half to even (round(2.5) == 2); the
    port must round half away from zero like Swift's .rounded(), matching
    everyday calculator behaviour. See PORTING.md 3.2.
    """
    assert_eval(evaluator, "round(2.5)", 3)
    assert_eval(evaluator, "round(3.5)", 4)
    assert_eval(evaluator, "round(-2.5)", -3)


# --- pow() overflow and domain behaviour -----------------------------------


def test_pow_overflow_returns_infinity(evaluator):
    """math.pow raises OverflowError where Swift's pow returns inf; the UI
    renders inf as the infinity symbol, so the port must return inf, not
    raise. See PORTING.md 3.3.
    """
    result = evaluator.evaluate("10^400")
    assert math.isinf(result) and result > 0


def test_pow_domain_error(evaluator):
    """A negative base with a fractional exponent has no real result --
    report it as a domain error rather than propagating a raw ValueError.
    """
    with pytest.raises(DomainError):
        evaluator.evaluate("(-8)^0.5")


# --- Percent -- bare form divides by 100 -----------------------------------


def test_percent_bare(evaluator):
    assert_eval(evaluator, "10%", 0.1)
    assert_eval(evaluator, "50%", 0.5)
    assert_eval(evaluator, "50%%", 0.005)  # stacked percents


# --- Percent -- calculator semantics: "y% of x" after + / - ----------------


def test_percent_additive(evaluator):
    assert_eval(evaluator, "100+10%", 110)  # 100 + 100*0.10
    assert_eval(evaluator, "100-10%", 90)  # 100 - 100*0.10
    assert_eval(evaluator, "50+50%", 75)
    assert_eval(evaluator, "((10^2-10)/9)+10%", 11)  # the originally reported bug
    assert_eval(evaluator, "1+2+10%", 3.3)  # 3 + 3*0.10


# --- Percent -- multiplicative uses the raw fraction -----------------------


def test_percent_multiplicative(evaluator):
    assert_eval(evaluator, "200*10%", 20)  # 200 * 0.10
    assert_eval(evaluator, "200/10%", 2000)  # 200 / 0.10
    assert_eval(evaluator, "100+2*3%", 100.06)  # 100 + (2*0.03)


# --- Whitespace ---------------------------------------------------------


def test_whitespace_tolerance(evaluator):
    assert_eval(evaluator, "  1  +   2 ", 3)


# --- Errors -----------------------------------------------------------------


def test_errors(evaluator):
    assert_throws(evaluator, "1/0")
    assert_throws(evaluator, "10 mod 0")
    assert_throws(evaluator, "sqrt(-1)")
    assert_throws(evaluator, "ln(-1)")
    assert_throws(evaluator, "log(0)")
    assert_throws(evaluator, "(1+2")  # unbalanced parens
    assert_throws(evaluator, "1+")  # trailing operator
    assert_throws(evaluator, "foo")  # unknown identifier
    assert_throws(evaluator, "1 2")  # trailing token


def test_division_by_zero_error_type(evaluator):
    with pytest.raises(DivisionByZeroError):
        evaluator.evaluate("1/0")


def test_unknown_identifier_error_type(evaluator):
    with pytest.raises(UnknownIdentifierError):
        evaluator.evaluate("foo")


def test_unbalanced_parens_error_type(evaluator):
    with pytest.raises(UnexpectedEndError):
        evaluator.evaluate("(1+2")


def test_malformed_number(evaluator):
    """The Swift lexer silently turns a malformed literal into 0 via
    `Double(num) ?? 0`. The port raises instead of returning a wrong
    answer. See PORTING.md 3.6.
    """
    with pytest.raises(MalformedNumberError):
        evaluator.evaluate("1.2.3")


# --- Shortcuts / user constants ---------------------------------------------


def test_user_constants_override_builtins():
    evaluator = ExpressionEvaluator(constants={"pi": 3.0})
    assert_eval(evaluator, "pi", 3.0)


def test_user_constants():
    evaluator = ExpressionEvaluator(constants={"usd": 1.08})
    assert_eval(evaluator, "100*usd", 108)

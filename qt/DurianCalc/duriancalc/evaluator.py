"""Evaluates mathematical expression strings with correct operator
precedence, parentheses, and built-in functions -- the core of an
expression-based calculator like pearCalc.

Grammar (lowest to highest precedence):
    expression := term (("+" | "-") term)*
    term       := unary (("*" | "/" | "mod") unary)*
    unary      := ("+" | "-") unary | power    // binds looser than ^
    power      := postfix ("^" unary)?         // right-associative
    postfix    := primary "%"*
    primary    := number | constant | ident "(" expression ")" | "(" expression ")"

A trailing `%` divides by 100, but when it follows a `+` or `-` it is
interpreted as a percentage *of the left operand* -- the familiar
calculator behaviour where `100 + 10%` is `110`, not `100.1`.

This is a port of the macOS Swift evaluator (../../mac/DurianCalc/DurianCalc/
ExpressionEvaluator.swift). See PORTING.md section 3 for the numeric
differences between Swift and Python that this port deliberately corrects
for (mod sign convention, round() half-to-even, pow() overflow/domain
behaviour, Unicode character classes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto


class EvalError(Exception):
    """Base class for all expression evaluation errors."""


class UnexpectedCharacterError(EvalError):
    def __init__(self, char: str):
        super().__init__(f"Unexpected character '{char}'")


class MalformedNumberError(EvalError):
    def __init__(self, text: str):
        super().__init__(f"Malformed number '{text}'")


class UnexpectedTokenError(EvalError):
    def __init__(self, token_desc: str):
        super().__init__(f"Unexpected '{token_desc}'")


class UnexpectedEndError(EvalError):
    def __init__(self):
        super().__init__("Incomplete expression")


class UnknownIdentifierError(EvalError):
    def __init__(self, name: str):
        super().__init__(f"Unknown name '{name}'")


class DivisionByZeroError(EvalError):
    def __init__(self):
        super().__init__("Division by zero")


class DomainError(EvalError):
    def __init__(self, message: str):
        super().__init__(message)


# --- Tokens ---------------------------------------------------------------


class TokenKind(Enum):
    NUMBER = auto()
    IDENTIFIER = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    CARET = auto()
    PERCENT = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: object = None  # float for NUMBER, str for IDENTIFIER

    def describe(self) -> str:
        if self.kind is TokenKind.NUMBER:
            return _format_token_number(self.value)
        if self.kind is TokenKind.IDENTIFIER:
            return str(self.value)
        return {
            TokenKind.PLUS: "+",
            TokenKind.MINUS: "-",
            TokenKind.STAR: "*",
            TokenKind.SLASH: "/",
            TokenKind.CARET: "^",
            TokenKind.PERCENT: "%",
            TokenKind.LPAREN: "(",
            TokenKind.RPAREN: ")",
            TokenKind.COMMA: ",",
        }[self.kind]


def _format_token_number(n: float) -> str:
    if n == int(n) and abs(n) < 1e15:
        return str(int(n))
    return str(n)


_SIMPLE_TOKENS = {
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "×": TokenKind.STAR,  # ×
    "/": TokenKind.SLASH,
    "÷": TokenKind.SLASH,  # ÷
    "^": TokenKind.CARET,
    "%": TokenKind.PERCENT,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    ",": TokenKind.COMMA,
}


def _is_ascii_digit(c: str) -> bool:
    return "0" <= c <= "9"


def _is_ascii_letter(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def tokenize(text: str) -> list[Token]:
    """Deliberately ASCII-only: Swift's Character.isNumber/isLetter accept a
    much wider Unicode range than anyone actually types into a calculator
    (Arabic-Indic digits, accented letters, superscripts, ...). Restricting
    to ASCII keeps the lexer predictable. See PORTING.md section 3.4.
    """
    tokens: list[Token] = []
    chars = text
    i = 0
    n = len(chars)

    while i < n:
        c = chars[i]

        if c.isspace():
            i += 1
            continue

        if _is_ascii_digit(c) or c == ".":
            start = i
            while i < n and (_is_ascii_digit(chars[i]) or chars[i] == "."):
                i += 1
            # Support scientific notation like 1e3 or 2.5e-4.
            if i < n and chars[i] in ("e", "E"):
                save = i
                j = i + 1
                if j < n and chars[j] in ("+", "-"):
                    j += 1
                if j < n and _is_ascii_digit(chars[j]):
                    j += 1
                    while j < n and _is_ascii_digit(chars[j]):
                        j += 1
                    i = j
                else:
                    i = save  # "e" was actually an identifier; back off.
            num_text = chars[start:i]
            try:
                value = float(num_text)
            except ValueError:
                raise MalformedNumberError(num_text) from None
            tokens.append(Token(TokenKind.NUMBER, value))
            continue

        if _is_ascii_letter(c) or c == "_":
            start = i
            while i < n and (_is_ascii_letter(chars[i]) or _is_ascii_digit(chars[i]) or chars[i] == "_"):
                i += 1
            tokens.append(Token(TokenKind.IDENTIFIER, chars[start:i].lower()))
            continue

        if c in _SIMPLE_TOKENS:
            tokens.append(Token(_SIMPLE_TOKENS[c]))
            i += 1
            continue

        raise UnexpectedCharacterError(c)

    return tokens


# --- Parser / evaluator -----------------------------------------------------

_BUILTIN_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _round_half_away_from_zero(x: float) -> float:
    """Swift's Double.rounded() rounds half away from zero; Python's round()
    rounds half to even (banker's rounding). round(2.5) must be 3, not 2 --
    see PORTING.md section 3.2.
    """
    return math.copysign(math.floor(abs(x) + 0.5), x)


def _pow(base: float, exponent: float) -> float:
    """Mirrors Swift's `pow`: overflow saturates to +/-inf (rendered as the
    infinity symbol by the UI) rather than raising, but a genuine domain
    error (e.g. a fractional power of a negative base) is reported as such.
    See PORTING.md section 3.3.
    """
    try:
        return math.pow(base, exponent)
    except OverflowError:
        sign = -1.0 if (base < 0 and int(exponent) % 2 != 0) else 1.0
        return math.inf * sign
    except ValueError:
        raise DomainError(f"{base} ^ {exponent} is not a real number") from None


def _apply_function(name: str, x: float) -> float:
    if name == "sin":
        return math.sin(x)
    if name == "cos":
        return math.cos(x)
    if name == "tan":
        return math.tan(x)
    if name == "asin":
        return math.asin(x)
    if name == "acos":
        return math.acos(x)
    if name == "atan":
        return math.atan(x)
    if name == "sinh":
        return math.sinh(x)
    if name == "cosh":
        return math.cosh(x)
    if name == "tanh":
        return math.tanh(x)
    if name == "ln":
        if not x > 0:
            raise DomainError("ln needs a positive number")
        return math.log(x)
    if name in ("log", "log10"):
        if not x > 0:
            raise DomainError("log needs a positive number")
        return math.log10(x)
    if name == "log2":
        if not x > 0:
            raise DomainError("log2 needs a positive number")
        return math.log2(x)
    if name == "sqrt":
        if not x >= 0:
            raise DomainError("sqrt needs a non-negative number")
        return math.sqrt(x)
    if name == "cbrt":
        return math.copysign(abs(x) ** (1 / 3), x)
    if name == "abs":
        return abs(x)
    if name == "exp":
        return math.exp(x)
    if name == "floor":
        return math.floor(x)
    if name == "ceil":
        return math.ceil(x)
    if name == "round":
        return _round_half_away_from_zero(x)
    if name == "rad":
        return x * math.pi / 180  # degrees -> radians
    if name == "deg":
        return x * 180 / math.pi  # radians -> degrees
    raise UnknownIdentifierError(name)


class _Parser:
    def __init__(self, tokens: list[Token], constants: dict[str, float]):
        self.tokens = tokens
        self.constants = constants
        self.pos = 0
        # Set by _parse_postfix when the most recently parsed operand ended
        # in a trailing `%` that was *not* subsequently combined with
        # another operator. _parse_expression uses this to give `x + y%`
        # its calculator meaning: "y percent of x" rather than a bare
        # y/100.
        self.last_was_percent = False

    @property
    def current(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> Token | None:
        tok = self.current
        self.pos += 1
        return tok

    def _at(self, kind: TokenKind) -> bool:
        tok = self.current
        return tok is not None and tok.kind is kind

    def expect_end(self) -> None:
        if self.current is not None:
            raise UnexpectedTokenError(self.current.describe())

    # expression := term (("+" | "-") term)*
    def parse_expression(self) -> float:
        value = self.parse_term()
        while self._at(TokenKind.PLUS) or self._at(TokenKind.MINUS):
            is_plus = self._at(TokenKind.PLUS)
            self.pos += 1
            rhs = self.parse_term()
            # `x + y%` means "add y percent *of x*", i.e. x + x*(y/100).
            # `rhs` already holds y/100 from the trailing `%`, so the
            # extra factor is just the accumulated left value.
            delta = value * rhs if self.last_was_percent else rhs
            value = value + delta if is_plus else value - delta
        return value

    # term := unary (("*" | "/" | "mod") unary)*
    def parse_term(self) -> float:
        value = self.parse_unary()
        while True:
            tok = self.current
            if tok is None:
                break
            if tok.kind is TokenKind.STAR or tok.kind is TokenKind.SLASH:
                is_slash = tok.kind is TokenKind.SLASH
                self.pos += 1
                rhs = self.parse_unary()
                if is_slash:
                    if rhs == 0:
                        raise DivisionByZeroError()
                    value /= rhs
                else:
                    value *= rhs
            elif tok.kind is TokenKind.IDENTIFIER and tok.value == "mod":
                self.pos += 1
                rhs = self.parse_unary()
                if rhs == 0:
                    raise DivisionByZeroError()
                # Floored modulo: sign follows the divisor (`-10 mod 3` is
                # `2`), which is what Python's `%` already does. The mac
                # Swift evaluator deliberately matches this too -- see
                # PORTING.md section 3.1.
                value = value % rhs
            else:
                break
            # A product/quotient/remainder is a concrete value, not a
            # pending percentage -- clear the flag so an enclosing +/-
            # treats it literally.
            self.last_was_percent = False
        return value

    # unary := ("+" | "-") unary | power
    # Unary minus binds looser than "^", so -2^2 == -(2^2) == -4, matching
    # standard mathematical convention.
    def parse_unary(self) -> float:
        if self._at(TokenKind.MINUS):
            self.pos += 1
            return -self.parse_unary()
        if self._at(TokenKind.PLUS):
            self.pos += 1
            return self.parse_unary()
        return self.parse_power()

    # power := postfix ("^" unary)?   -- right-associative; exponent may be signed
    def parse_power(self) -> float:
        base = self.parse_postfix()
        if self._at(TokenKind.CARET):
            self.pos += 1
            exponent = self.parse_unary()
            self.last_was_percent = False
            return _pow(base, exponent)
        return base

    # postfix := primary "%"*   -- trailing percent means "divide by 100"
    def parse_postfix(self) -> float:
        value = self.parse_primary()
        is_percent = False
        while self._at(TokenKind.PERCENT):
            self.pos += 1
            value /= 100
            is_percent = True
        self.last_was_percent = is_percent
        return value

    # primary := number | ident | ident "(" expr ")" | "(" expr ")"
    def parse_primary(self) -> float:
        tok = self.advance()
        if tok is None:
            raise UnexpectedEndError()

        if tok.kind is TokenKind.NUMBER:
            return tok.value

        if tok.kind is TokenKind.LPAREN:
            value = self.parse_expression()
            if not self._at(TokenKind.RPAREN):
                raise UnexpectedEndError()
            self.pos += 1
            return value

        if tok.kind is TokenKind.IDENTIFIER:
            name = tok.value
            # Function call?
            if self._at(TokenKind.LPAREN):
                self.pos += 1
                arg = self.parse_expression()
                if not self._at(TokenKind.RPAREN):
                    raise UnexpectedEndError()
                self.pos += 1
                return _apply_function(name, arg)
            # Otherwise a constant / shortcut.
            if name in self.constants:
                return self.constants[name]
            raise UnknownIdentifierError(name)

        raise UnexpectedTokenError(tok.describe())


@dataclass
class ExpressionEvaluator:
    """User-defined constants/shortcuts, e.g. {"usd": 1.08}. Merged over
    built-ins (user values win on name collision).
    """

    constants: dict[str, float] = field(default_factory=dict)

    def evaluate(self, text: str) -> float:
        merged = {**_BUILTIN_CONSTANTS, **self.constants}
        parser = _Parser(tokenize(text), merged)
        value = parser.parse_expression()
        parser.expect_end()
        return value

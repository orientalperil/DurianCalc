import Foundation

/// Evaluates mathematical expression strings with correct operator
/// precedence, parentheses, and built-in functions — the core of
/// an expression-based calculator like pearCalc.
///
/// Grammar (lowest to highest precedence):
///   expression := term (("+" | "-") term)*
///   term       := unary (("*" | "/" | "mod") unary)*
///   unary      := ("+" | "-") unary | power    // binds looser than ^
///   power      := postfix ("^" unary)?         // right-associative
///   postfix    := primary "%"*
///   primary    := number | constant | ident "(" expression ")" | "(" expression ")"
///
/// A trailing `%` divides by 100, but when it follows a `+` or `-` it is
/// interpreted as a percentage *of the left operand* — the familiar
/// calculator behaviour where `100 + 10%` is `110`, not `100.1`.
struct ExpressionEvaluator {

    enum EvalError: Error, LocalizedError {
        case unexpectedCharacter(Character)
        case unexpectedToken(String)
        case unexpectedEnd
        case unknownIdentifier(String)
        case divisionByZero
        case domainError(String)

        var errorDescription: String? {
            switch self {
            case .unexpectedCharacter(let c): return "Unexpected character '\(c)'"
            case .unexpectedToken(let t): return "Unexpected '\(t)'"
            case .unexpectedEnd: return "Incomplete expression"
            case .unknownIdentifier(let name): return "Unknown name '\(name)'"
            case .divisionByZero: return "Division by zero"
            case .domainError(let msg): return msg
            }
        }
    }

    /// User-defined constants/shortcuts, e.g. ["usd": 1.08]. Merged over built-ins.
    var constants: [String: Double] = [:]

    private static let builtinConstants: [String: Double] = [
        "pi": .pi,
        "e": M_E,
        "tau": 2 * .pi
    ]

    // MARK: - Public entry point

    func evaluate(_ input: String) throws -> Double {
        var parser = Parser(
            tokens: try Lexer.tokenize(input),
            constants: constants.merging(Self.builtinConstants) { user, _ in user }
        )
        let value = try parser.parseExpression()
        try parser.expectEnd()
        return value
    }

    // MARK: - Tokens

    enum Token: Equatable {
        case number(Double)
        case identifier(String)
        case plus, minus, star, slash, caret, percent
        case lparen, rparen, comma
    }

    // MARK: - Lexer

    private enum Lexer {
        static func tokenize(_ input: String) throws -> [Token] {
            var tokens: [Token] = []
            let chars = Array(input)
            var i = 0

            while i < chars.count {
                let c = chars[i]

                if c.isWhitespace {
                    i += 1
                    continue
                }

                if c.isNumber || c == "." {
                    var num = ""
                    while i < chars.count, chars[i].isNumber || chars[i] == "." {
                        num.append(chars[i])
                        i += 1
                    }
                    // Support scientific notation like 1e3 or 2.5e-4.
                    if i < chars.count, chars[i] == "e" || chars[i] == "E" {
                        let save = i
                        var exp = String(chars[i]); i += 1
                        if i < chars.count, chars[i] == "+" || chars[i] == "-" {
                            exp.append(chars[i]); i += 1
                        }
                        if i < chars.count, chars[i].isNumber {
                            while i < chars.count, chars[i].isNumber {
                                exp.append(chars[i]); i += 1
                            }
                            num += exp
                        } else {
                            i = save // "e" was actually an identifier; back off.
                        }
                    }
                    tokens.append(.number(Double(num) ?? 0))
                    continue
                }

                if c.isLetter || c == "_" {
                    var name = ""
                    while i < chars.count, chars[i].isLetter || chars[i].isNumber || chars[i] == "_" {
                        name.append(chars[i])
                        i += 1
                    }
                    tokens.append(.identifier(name.lowercased()))
                    continue
                }

                switch c {
                case "+": tokens.append(.plus)
                case "-": tokens.append(.minus)
                case "*", "×": tokens.append(.star)
                case "/", "÷": tokens.append(.slash)
                case "^": tokens.append(.caret)
                case "%": tokens.append(.percent)
                case "(": tokens.append(.lparen)
                case ")": tokens.append(.rparen)
                case ",": tokens.append(.comma)
                default:
                    throw EvalError.unexpectedCharacter(c)
                }
                i += 1
            }
            return tokens
        }
    }

    // MARK: - Parser / evaluator

    private struct Parser {
        let tokens: [Token]
        let constants: [String: Double]
        var pos = 0

        /// Set by `parsePostfix` when the most recently parsed operand ended
        /// in a trailing `%` that was *not* subsequently combined with another
        /// operator. `parseExpression` uses this to give `x + y%` its
        /// calculator meaning: "y percent of x" rather than a bare `y/100`.
        var lastWasPercent = false

        init(tokens: [Token], constants: [String: Double]) {
            self.tokens = tokens
            self.constants = constants
        }

        var current: Token? { pos < tokens.count ? tokens[pos] : nil }

        mutating func advance() -> Token? {
            defer { pos += 1 }
            return current
        }

        func expectEnd() throws {
            if let tok = current {
                throw EvalError.unexpectedToken(describe(tok))
            }
        }

        // expression := term (("+" | "-") term)*
        mutating func parseExpression() throws -> Double {
            var value = try parseTerm()
            while let tok = current, tok == .plus || tok == .minus {
                pos += 1
                let rhs = try parseTerm()
                // `x + y%` means "add y percent *of x*", i.e. x + x*(y/100).
                // `rhs` already holds y/100 from the trailing `%`, so the
                // extra factor is just the accumulated left value.
                let delta = lastWasPercent ? value * rhs : rhs
                value = (tok == .plus) ? value + delta : value - delta
            }
            return value
        }

        // term := unary (("*" | "/" | "mod" | "%") unary)*
        mutating func parseTerm() throws -> Double {
            var value = try parseUnary()
            while let tok = current {
                if tok == .star || tok == .slash {
                    pos += 1
                    let rhs = try parseUnary()
                    if tok == .slash {
                        guard rhs != 0 else { throw EvalError.divisionByZero }
                        value /= rhs
                    } else {
                        value *= rhs
                    }
                } else if tok == .identifier("mod") {
                    pos += 1
                    let rhs = try parseUnary()
                    guard rhs != 0 else { throw EvalError.divisionByZero }
                    value = value.truncatingRemainder(dividingBy: rhs)
                } else {
                    break
                }
                // A product/quotient/remainder is a concrete value, not a
                // pending percentage — clear the flag so an enclosing `+`/`-`
                // treats it literally.
                lastWasPercent = false
            }
            return value
        }

        // unary := ("+" | "-") unary | power
        // Unary minus binds looser than "^", so -2^2 == -(2^2) == -4,
        // matching standard mathematical convention.
        mutating func parseUnary() throws -> Double {
            if current == .minus {
                pos += 1
                return -(try parseUnary())
            }
            if current == .plus {
                pos += 1
                return try parseUnary()
            }
            return try parsePower()
        }

        // power := postfix ("^" unary)?   — right-associative; exponent may be signed
        mutating func parsePower() throws -> Double {
            let base = try parsePostfix()
            if current == .caret {
                pos += 1
                let exponent = try parseUnary()
                lastWasPercent = false
                return pow(base, exponent)
            }
            return base
        }

        // postfix := primary "%"?   — trailing percent means "divide by 100"
        mutating func parsePostfix() throws -> Double {
            var value = try parsePrimary()
            var isPercent = false
            while current == .percent {
                pos += 1
                value /= 100
                isPercent = true
            }
            lastWasPercent = isPercent
            return value
        }

        // primary := number | ident | ident "(" expr ")" | "(" expr ")"
        mutating func parsePrimary() throws -> Double {
            guard let tok = advance() else { throw EvalError.unexpectedEnd }

            switch tok {
            case .number(let n):
                return n

            case .lparen:
                let value = try parseExpression()
                guard current == .rparen else { throw EvalError.unexpectedEnd }
                pos += 1
                return value

            case .identifier(let name):
                // Function call?
                if current == .lparen {
                    pos += 1
                    let arg = try parseExpression()
                    guard current == .rparen else { throw EvalError.unexpectedEnd }
                    pos += 1
                    return try applyFunction(name, arg)
                }
                // Otherwise a constant / shortcut.
                if let value = constants[name] {
                    return value
                }
                throw EvalError.unknownIdentifier(name)

            default:
                throw EvalError.unexpectedToken(describe(tok))
            }
        }

        func applyFunction(_ name: String, _ x: Double) throws -> Double {
            switch name {
            case "sin": return sin(x)
            case "cos": return cos(x)
            case "tan": return tan(x)
            case "asin": return asin(x)
            case "acos": return acos(x)
            case "atan": return atan(x)
            case "sinh": return sinh(x)
            case "cosh": return cosh(x)
            case "tanh": return tanh(x)
            case "ln": 
                guard x > 0 else { throw EvalError.domainError("ln needs a positive number") }
                return log(x)
            case "log", "log10":
                guard x > 0 else { throw EvalError.domainError("log needs a positive number") }
                return log10(x)
            case "log2":
                guard x > 0 else { throw EvalError.domainError("log2 needs a positive number") }
                return log2(x)
            case "sqrt":
                guard x >= 0 else { throw EvalError.domainError("sqrt needs a non-negative number") }
                return sqrt(x)
            case "cbrt": return cbrt(x)
            case "abs": return abs(x)
            case "exp": return exp(x)
            case "floor": return floor(x)
            case "ceil": return ceil(x)
            case "round": return x.rounded()
            case "rad": return x * .pi / 180   // degrees -> radians
            case "deg": return x * 180 / .pi   // radians -> degrees
            default:
                throw EvalError.unknownIdentifier(name)
            }
        }

        func describe(_ tok: Token) -> String {
            switch tok {
            case .number(let n): return "\(n)"
            case .identifier(let s): return s
            case .plus: return "+"
            case .minus: return "-"
            case .star: return "*"
            case .slash: return "/"
            case .caret: return "^"
            case .percent: return "%"
            case .lparen: return "("
            case .rparen: return ")"
            case .comma: return ","
            }
        }
    }
}

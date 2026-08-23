import XCTest
@testable import DurianCalc

final class ExpressionEvaluatorTests: XCTestCase {

    private let evaluator = ExpressionEvaluator()

    /// Asserts `expr` evaluates to `expected` within a small tolerance.
    private func assertEval(_ expr: String,
                            _ expected: Double,
                            accuracy: Double = 1e-9,
                            file: StaticString = #filePath,
                            line: UInt = #line) {
        do {
            let got = try evaluator.evaluate(expr)
            XCTAssertEqual(got, expected, accuracy: accuracy,
                           "\(expr)", file: file, line: line)
        } catch {
            XCTFail("\(expr) threw \(error)", file: file, line: line)
        }
    }

    /// Asserts `expr` throws during evaluation.
    private func assertThrows(_ expr: String,
                              file: StaticString = #filePath,
                              line: UInt = #line) {
        XCTAssertThrowsError(try evaluator.evaluate(expr),
                             "\(expr) should have thrown",
                             file: file, line: line)
    }

    // MARK: Basic arithmetic

    func testBasicArithmetic() {
        assertEval("1+2", 3)
        assertEval("10-4", 6)
        assertEval("6*7", 42)
        assertEval("20/5", 4)
        assertEval("2.5+2.5", 5)
    }

    // MARK: Precedence & parentheses

    func testPrecedenceAndParentheses() {
        assertEval("2+3*4", 14)
        assertEval("(2+3)*4", 20)
        assertEval("2+3*4-6/2", 11)
        assertEval("((10^2-10)/9)", 10)
    }

    // MARK: Unary operators

    func testUnaryOperators() {
        assertEval("-5", -5)
        assertEval("-(3+2)", -5)
        assertEval("3--2", 5)      // 3 - (-2)
        assertEval("+-+7", -7)
    }

    // MARK: Exponentiation (right-associative; unary binds looser than ^)

    func testExponentiation() {
        assertEval("2^3", 8)
        assertEval("2^3^2", 512)   // 2^(3^2), not (2^3)^2 = 64
        assertEval("-2^2", -4)     // -(2^2), standard convention
        assertEval("2^-1", 0.5)
    }

    // MARK: mod

    func testModulo() {
        assertEval("10 mod 3", 1)
        assertEval("10 mod 2", 0)
    }

    // MARK: Constants

    func testConstants() {
        assertEval("pi", .pi)
        assertEval("2*pi", 2 * .pi)
        assertEval("tau", 2 * .pi)
    }

    // MARK: Functions

    func testFunctions() {
        assertEval("sqrt(9)", 3)
        assertEval("abs(-4)", 4)
        assertEval("floor(3.7)", 3)
        assertEval("ceil(3.2)", 4)
        assertEval("round(2.5)", 3)
        assertEval("ln(e)", 1)
        assertEval("log(1000)", 3)
        assertEval("log2(8)", 3)
        assertEval("sin(0)", 0)
        assertEval("cos(0)", 1)
    }

    // MARK: Percent — bare form divides by 100

    func testPercentBare() {
        assertEval("10%", 0.1)
        assertEval("50%", 0.5)
        assertEval("50%%", 0.005)  // stacked percents
    }

    // MARK: Percent — calculator semantics: "y% of x" after + / -

    func testPercentAdditive() {
        assertEval("100+10%", 110)               // 100 + 100*0.10
        assertEval("100-10%", 90)                // 100 - 100*0.10
        assertEval("50+50%", 75)
        assertEval("((10^2-10)/9)+10%", 11)      // the originally reported bug
        assertEval("1+2+10%", 3.3)               // 3 + 3*0.10
    }

    // MARK: Percent — multiplicative uses the raw fraction and clears the
    // "pending percent" so an enclosing +/- treats the result literally.

    func testPercentMultiplicative() {
        assertEval("200*10%", 20)                // 200 * 0.10
        assertEval("200/10%", 2000)              // 200 / 0.10
        assertEval("100+2*3%", 100.06)           // 100 + (2*0.03)
    }

    // MARK: Whitespace

    func testWhitespaceTolerance() {
        assertEval("  1  +   2 ", 3)
    }

    // MARK: Errors

    func testErrors() {
        assertThrows("1/0")
        assertThrows("10 mod 0")
        assertThrows("sqrt(-1)")
        assertThrows("ln(-1)")
        assertThrows("log(0)")
        assertThrows("(1+2")        // unbalanced parens
        assertThrows("1+")          // trailing operator
        assertThrows("foo")         // unknown identifier
        assertThrows("1 2")         // trailing token
    }
}

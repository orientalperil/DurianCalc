import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var shortcuts: ShortcutStore

    @State private var expression: String = ""
    @State private var result: String = ""
    @State private var isError: Bool = false
    @State private var history: [String] = []
    @FocusState private var fieldFocused: Bool

    // Pear-green accent, tuned to read well on a light background.
    private let accent = Color(red: 0.36, green: 0.62, blue: 0.20)

    private let numberFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.maximumFractionDigits = 10
        f.usesGroupingSeparator = false
        return f
    }()

    var body: some View {
        VStack(spacing: 0) {
            inputRow
            if !result.isEmpty {
                Divider()
                resultRow
            }
        }
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Color.black.opacity(0.12), lineWidth: 1)
        )
        .padding(10)
        .frame(width: 440)
        .background(EscKeyHandler { clearAll() })   // ESC anywhere clears.
        .onAppear { fieldFocused = true }
    }

    // The single expression field — the whole point of the app.
    private var inputRow: some View {
        HStack(spacing: 10) {
            TextField("", text: $expression)
                .textFieldStyle(.plain)
                .font(.system(size: 20, weight: .regular, design: .rounded))
                .foregroundColor(.primary)
                .focused($fieldFocused)
                .onChange(of: expression) { _ in liveEvaluate() }
                .onSubmit { commit() }

            if !expression.isEmpty {
                Button {
                    clearAll()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Clear (Esc)")
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var resultRow: some View {
        HStack {
            Text(isError ? "⚠︎" : "=")
                .foregroundColor(isError ? .orange : accent)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
            Text(result)
                .font(.system(size: 22, weight: .medium, design: .rounded))
                .foregroundColor(isError ? .orange : .primary)
                .textSelection(.enabled)
                .lineLimit(1)
                .minimumScaleFactor(0.5)
            Spacer()
            if !isError && !result.isEmpty {
                Button {
                    copyResult()
                } label: {
                    Image(systemName: "doc.on.doc")
                        .foregroundColor(.secondary)
                        .font(.system(size: 13))
                }
                .buttonStyle(.plain)
                .help("Copy result")
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    // MARK: - Actions

    private func clearAll() {
        expression = ""
        result = ""
        isError = false
        fieldFocused = true
    }

    // MARK: - Evaluation

    private func liveEvaluate() {
        let trimmed = expression.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            result = ""
            isError = false
            return
        }

        var evaluator = ExpressionEvaluator()
        evaluator.constants = shortcuts.asConstants

        do {
            let value = try evaluator.evaluate(trimmed)
            result = format(value)
            isError = false
        } catch {
            // While typing, show a gentle hint rather than a hard error.
            result = (error as? ExpressionEvaluator.EvalError)?.errorDescription ?? "…"
            isError = true
        }
    }

    private func commit() {
        guard !isError, !result.isEmpty else { return }
        history.insert("\(expression) = \(result)", at: 0)
        // Feed the result back in, so you can keep calculating from it.
        expression = result
        fieldFocused = true
    }

    private func copyResult() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(result, forType: .string)
    }

    private func format(_ value: Double) -> String {
        if value.isNaN { return "not a number" }
        if value.isInfinite { return value < 0 ? "-∞" : "∞" }
        if value == value.rounded() && abs(value) < 1e15 {
            return String(format: "%.0f", value)
        }
        return numberFormatter.string(from: NSNumber(value: value)) ?? String(value)
    }
}

/// Intercepts the Escape key and runs a handler, reliably — even inside an
/// NSPanel, where Escape would otherwise trigger cancelOperation and close the
/// window. A local NSEvent monitor sees the keyDown before the panel acts on it.
struct EscKeyHandler: NSViewRepresentable {
    let onEscape: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onEscape: onEscape) }

    func makeNSView(context: Context) -> NSView {
        context.coordinator.start()
        return NSView()
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        context.coordinator.onEscape = onEscape
    }

    static func dismantleNSView(_ nsView: NSView, coordinator: Coordinator) {
        coordinator.stop()
    }

    final class Coordinator {
        var onEscape: () -> Void
        private var monitor: Any?

        init(onEscape: @escaping () -> Void) { self.onEscape = onEscape }

        func start() {
            monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
                if event.keyCode == 53 {          // 53 == Escape
                    self?.onEscape()
                    return nil                     // Swallow it so the panel won't close.
                }
                return event
            }
        }

        func stop() {
            if let monitor { NSEvent.removeMonitor(monitor) }
            monitor = nil
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(ShortcutStore())
}

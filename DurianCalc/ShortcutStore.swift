import Foundation

/// A user-defined shortcut: a name that expands to a value inside expressions.
/// In pearCalc these are used for currency conversion (e.g. "usd" -> 1.08)
/// or as named constants.
struct Shortcut: Identifiable, Codable, Equatable {
    var id = UUID()
    var name: String
    var value: Double
}

/// Persists the shortcut list to UserDefaults and exposes it as constants
/// for the evaluator.
final class ShortcutStore: ObservableObject {
    @Published var shortcuts: [Shortcut] {
        didSet { save() }
    }

    private let defaultsKey = "duriancalc.shortcuts"

    init() {
        if let data = UserDefaults.standard.data(forKey: defaultsKey),
           let decoded = try? JSONDecoder().decode([Shortcut].self, from: data) {
            shortcuts = decoded
        } else {
            // A couple of sensible starter examples.
            shortcuts = [
                Shortcut(name: "usd", value: 1.08),
                Shortcut(name: "golden", value: 1.618)
            ]
        }
    }

    /// Name -> value map for feeding into the evaluator.
    var asConstants: [String: Double] {
        var dict: [String: Double] = [:]
        for s in shortcuts where !s.name.isEmpty {
            dict[s.name.lowercased()] = s.value
        }
        return dict
    }

    func add() {
        shortcuts.append(Shortcut(name: "new", value: 0))
    }

    func remove(at offsets: IndexSet) {
        shortcuts.remove(atOffsets: offsets)
    }

    private func save() {
        if let data = try? JSONEncoder().encode(shortcuts) {
            UserDefaults.standard.set(data, forKey: defaultsKey)
        }
    }
}

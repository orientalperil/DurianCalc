import SwiftUI

/// Preferences pane for defining shortcuts/constants, mirroring pearCalc's
/// shortcut list used for currency conversion and named constants.
struct ShortcutsView: View {
    @EnvironmentObject private var store: ShortcutStore

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Shortcuts & Constants")
                .font(.headline)
            Text("Use these names inside any expression — for example a currency rate or a constant of your own.")
                .font(.caption)
                .foregroundColor(.secondary)

            Table(of: Binding<Shortcut>.self) {
                TableColumn("Name") { $item in
                    TextField("name", text: $item.name)
                        .textFieldStyle(.roundedBorder)
                }
                TableColumn("Value") { $item in
                    TextField("value", value: $item.value, format: .number)
                        .textFieldStyle(.roundedBorder)
                }
            } rows: {
                ForEach($store.shortcuts) { $shortcut in
                    TableRow($shortcut)
                }
            }
            .frame(minHeight: 180)

            HStack {
                Button {
                    store.add()
                } label: {
                    Label("Add", systemImage: "plus")
                }
                Button(role: .destructive) {
                    if !store.shortcuts.isEmpty {
                        store.shortcuts.removeLast()
                    }
                } label: {
                    Label("Remove Last", systemImage: "minus")
                }
                Spacer()
            }

            Text("Built-in constants: pi, e, tau. Functions: sin, cos, tan, asin, acos, atan, ln, log, log2, sqrt, cbrt, abs, exp, floor, ceil, round, rad, deg. Operators: + − × ÷ ^ mod %.")
                .font(.caption2)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(20)
        .frame(width: 460)
    }
}

#Preview {
    ShortcutsView()
        .environmentObject(ShortcutStore())
}

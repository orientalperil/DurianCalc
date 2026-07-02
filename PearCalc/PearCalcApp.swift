import SwiftUI
import AppKit

@main
struct PearCalcApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        // The main calculator lives in a real NSPanel (see AppDelegate) so we
        // get the thin utility-window title bar. This Settings scene provides
        // the ⌘, preferences for editing shortcuts.
        Settings {
            ShortcutsView()
                .environmentObject(appDelegate.shortcuts)
                .preferredColorScheme(.light)
        }
    }
}

/// Owns the shortcut store and hosts the calculator UI in a utility panel —
/// the smaller "tool window" chrome (thin title bar) that AppKit calls a
/// utility window. A plain SwiftUI WindowGroup can't reliably produce this,
/// because the thin title bar is a property of NSPanel, not NSWindow.
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let shortcuts = ShortcutStore()
    private var panel: NSPanel!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)

        let root = ContentView()
            .environmentObject(shortcuts)
            .preferredColorScheme(.light)   // Always light mode.

        let hosting = NSHostingView(rootView: root)
        // Let the panel size itself to the SwiftUI content.
        hosting.translatesAutoresizingMaskIntoConstraints = false

        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 440, height: 80),
            styleMask: [.utilityWindow, .titled, .closable],  // <- thin title bar
            backing: .buffered,
            defer: false
        )
        panel.title = "pearCalc"
        panel.titlebarAppearsTransparent = true
        panel.isMovableByWindowBackground = true
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.becomesKeyOnlyIfNeeded = false
        panel.appearance = NSAppearance(named: .aqua)  // Force light chrome.
        panel.delegate = self  // So we can quit when the panel itself closes.

        // Wrap the hosting view so the panel hugs the content height.
        let container = NSView()
        container.addSubview(hosting)
        NSLayoutConstraint.activate([
            hosting.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            hosting.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            hosting.topAnchor.constraint(equalTo: container.topAnchor),
            hosting.bottomAnchor.constraint(equalTo: container.bottomAnchor),
        ])
        panel.contentView = container
        panel.center()
        panel.makeKeyAndOrderFront(nil)

        self.panel = panel
        NSApp.activate(ignoringOtherApps: true)
    }

    // Quit only when the user closes the calculator panel itself.
    //
    // We deliberately do NOT use applicationShouldTerminateAfterLastWindowClosed.
    // SwiftUI's `Settings` scene keeps a hidden backing window that opens and then
    // closes on its own shortly after launch. If we quit on "last window closed",
    // a fast relaunch (e.g. pressing Run in Xcode a second time, which kills and
    // immediately re-spawns the app) can close that phantom window during a window
    // where AppKit hasn't yet counted our panel as visible — so it reports the
    // last window as closed and terminates the app before it appears. Keying
    // termination off the panel's own close sidesteps that race.
    func windowWillClose(_ notification: Notification) {
        if (notification.object as? NSWindow) === panel {
            NSApp.terminate(nil)
        }
    }
}

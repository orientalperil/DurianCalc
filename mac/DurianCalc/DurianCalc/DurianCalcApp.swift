import SwiftUI
import AppKit

@main
struct DurianCalcApp: App {
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
            // `.resizable` enables the resize behavior; we then lock the height
            // (see contentMin/MaxSize below) so only the width can change.
            styleMask: [.utilityWindow, .titled, .closable, .resizable],  // <- thin title bar
            backing: .buffered,
            defer: false
        )
        panel.title = "DurianCalc"
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

        // Don't let the window be dragged narrower than the content can sensibly
        // shrink. Height is governed live in windowWillResize(_:to:).
        panel.contentMinSize = NSSize(width: 320, height: 0)

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
    // Allow horizontal resizing only. We can't just lock the height to a fixed
    // number, because the content's natural height changes as the result row
    // appears/disappears. So on every resize we take the user's proposed width
    // but override the height with whatever the content currently needs. This
    // keeps the top edge anchored instead of letting the frame jump.
    func windowWillResize(_ sender: NSWindow, to frameSize: NSSize) -> NSSize {
        guard let content = sender.contentView else { return frameSize }
        let chrome = sender.frame.height - content.frame.height  // title bar height
        let desiredContentHeight = content.fittingSize.height
        return NSSize(width: frameSize.width, height: desiredContentHeight + chrome)
    }

    func windowWillClose(_ notification: Notification) {
        if (notification.object as? NSWindow) === panel {
            NSApp.terminate(nil)
        }
    }
}

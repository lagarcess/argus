import SwiftUI
import WebKit

/// Hosts the Turnstile widget page and passes its events back to Swift.
/// The page, not the app, owns the widget; the app only receives the token.
struct TurnstileWebView: UIViewRepresentable {
    let page: URL
    let onInteractive: () -> Void
    let onEvent: (String, String?, String?) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onInteractive: onInteractive, onEvent: onEvent) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(context.coordinator, name: "turnstile")
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.load(URLRequest(url: page))
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {}

    static func dismantleUIView(_ view: WKWebView, coordinator: Coordinator) {
        view.configuration.userContentController.removeScriptMessageHandler(forName: "turnstile")
    }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        let onInteractive: () -> Void
        let onEvent: (String, String?, String?) -> Void
        private var settled = false

        init(onInteractive: @escaping () -> Void, onEvent: @escaping (String, String?, String?) -> Void) {
            self.onInteractive = onInteractive
            self.onEvent = onEvent
        }

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any], let event = body["event"] as? String else { return }
            if event == "interactive" { return onInteractive() }
            guard !settled else { return }
            settled = true
            onEvent(event, body["token"] as? String, body["detail"] as? String)
        }
    }
}

import SwiftUI
import WebKit

/// Only the configured main document may return a token. Each presentation owns
/// a fresh, nonpersistent web view and completes at most once.
struct CaptchaChallengeView: View {
    let sourceURL: URL
    let completion: (Result<String, CaptchaFailure>) -> Void
    @State private var completed = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            CaptchaWebView(sourceURL: sourceURL, completion: finish)
                .navigationTitle("auth.captcha.title")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("auth.cancel") { finish(.failure(.cancelled)) }
                            .accessibilityIdentifier("auth.captcha.cancel")
                    }
                }
                .task {
                    do {
                        try await Task.sleep(for: .seconds(90))
                        finish(.failure(.unavailable))
                    } catch { }
                }
        }
        .interactiveDismissDisabled()
        .accessibilityIdentifier("auth.captcha")
    }

    private func finish(_ result: Result<String, CaptchaFailure>) {
        guard !completed else { return }
        completed = true
        completion(result)
        dismiss()
    }
}

enum CaptchaFailure: Error { case cancelled, unavailable }

private struct CaptchaWebView: UIViewRepresentable {
    let sourceURL: URL
    let completion: (Result<String, CaptchaFailure>) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(sourceURL: sourceURL, completion: completion) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(context.coordinator, name: "argusCaptcha")
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.load(URLRequest(url: sourceURL, cachePolicy: .reloadIgnoringLocalCacheData))
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) { }

    static func dismantleUIView(_ view: WKWebView, coordinator: Coordinator) {
        coordinator.completed = true
        view.stopLoading()
        view.navigationDelegate = nil
        view.configuration.userContentController.removeScriptMessageHandler(forName: "argusCaptcha")
    }

    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        let sourceURL: URL
        let completion: (Result<String, CaptchaFailure>) -> Void
        var completed = false

        init(sourceURL: URL, completion: @escaping (Result<String, CaptchaFailure>) -> Void) {
            self.sourceURL = sourceURL
            self.completion = completion
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            guard !completed,
                  message.name == "argusCaptcha", message.frameInfo.isMainFrame,
                  message.frameInfo.request.url == sourceURL, message.webView?.url == sourceURL,
                  message.frameInfo.securityOrigin.protocol == sourceURL.scheme,
                  message.frameInfo.securityOrigin.host == sourceURL.host,
                  normalizedPort(message.frameInfo.securityOrigin.port) == (sourceURL.port ?? (sourceURL.scheme == "https" ? 443 : 80)),
                  let body = message.body as? [String: Any], let type = body["type"] as? String else {
                finish(.failure(.unavailable)); return
            }
            if type == "token", Set(body.keys) == ["type", "token"],
               let token = body["token"] as? String, !token.isEmpty,
               token.utf8.count <= 4096,
               token.unicodeScalars.allSatisfy({ !CharacterSet.whitespacesAndNewlines.contains($0) && !CharacterSet.controlCharacters.contains($0) }) {
                finish(.success(token))
            } else {
                finish(.failure(.unavailable))
            }
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let target = navigationAction.targetFrame, let url = navigationAction.request.url else {
                decisionHandler(.cancel); finish(.failure(.unavailable)); return
            }
            if target.isMainFrame {
                let allowed = url == sourceURL
                decisionHandler(allowed ? .allow : .cancel)
                if !allowed { finish(.failure(.unavailable)) }
            } else {
                let allowed = url == sourceURL ||
                    (url.scheme == "https" && url.host == "challenges.cloudflare.com" && url.user == nil && url.password == nil && (url.port == nil || url.port == 443))
                decisionHandler(allowed ? .allow : .cancel)
            }
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                     decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            if navigationResponse.isForMainFrame,
               (navigationResponse.response.url != sourceURL || (navigationResponse.response as? HTTPURLResponse)?.statusCode != 200) {
                decisionHandler(.cancel); finish(.failure(.unavailable))
            } else { decisionHandler(.allow) }
        }

        func webView(_ webView: WKWebView, didReceiveServerRedirectForProvisionalNavigation navigation: WKNavigation!) {
            if webView.url != sourceURL {
                webView.stopLoading()
                finish(.failure(.unavailable))
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            finish(.failure(.unavailable))
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            finish(.failure(.unavailable))
        }
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { finish(.failure(.unavailable)) }

        private func normalizedPort(_ port: Int) -> Int {
            port == 0 ? (sourceURL.scheme == "https" ? 443 : 80) : port
        }

        private func finish(_ result: Result<String, CaptchaFailure>) {
            guard !completed else { return }
            completed = true
            completion(result)
        }
    }
}

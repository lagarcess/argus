import ArgusNativeAuth
import Auth
import Foundation
import Observation

/// Drives the app-level checks: Turnstile in a web view and callback URL delivery.
/// Tokens and codes are never shown or logged; entries hold statuses and booleans.
@MainActor
@Observable
final class ProbeModel {
    struct Entry: Codable, Identifiable {
        var id = UUID()
        let step: String
        let observed: [String: String]
    }

    private(set) var entries: [Entry] = []
    var turnstilePage: URL?
    private var pendingRecoveryEmail: String?
    let client: ArgusNativeClient?

    private static func env(_ name: String) -> String? {
        ProcessInfo.processInfo.environment[name].flatMap { $0.isEmpty ? nil : $0 }
    }

    init() {
        if let anon = Self.env("NATIVE_AUTH_ANON_KEY") {
            client = ArgusNativeClient(
                stack: Stack(
                    argusAPI: URL(string: Self.env("NATIVE_AUTH_ARGUS_API") ?? "http://127.0.0.1:57460")!,
                    supabaseURL: URL(string: Self.env("NATIVE_AUTH_SUPABASE_URL") ?? "http://127.0.0.1:57451")!,
                    anonKey: anon
                ),
                keychainService: "local.argus.native-auth-proof.app",
                callback: URL(string: "argusnativeproof://auth-callback")!,
                deviceIP: Self.env("NATIVE_AUTH_DEVICE_IP")
            )
        } else {
            client = nil
        }
    }

    func log(_ step: String, _ observed: [String: String]) {
        entries.append(Entry(step: step, observed: observed))
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appending(path: "probe-log.json")
        try? JSONEncoder().encode(entries).write(to: url)
    }

    func autorun() async {
        let arguments = UserDefaults.standard
        log("launch", ["configured": String(client != nil)])
        switch arguments.string(forKey: "autorun") {
        case "turnstile":
            openTurnstile(sitekey: arguments.string(forKey: "sitekey") ?? "1x00000000000000000000AA")
        case "recovery":
            // Supabase requires a captcha token on /recover too, so recovery
            // runs behind the same web-view check as sign-in.
            pendingRecoveryEmail = arguments.string(forKey: "recoveryEmail")
            openTurnstile(sitekey: arguments.string(forKey: "sitekey") ?? "1x00000000000000000000AA")
        default:
            break
        }
    }

    func openTurnstile(sitekey: String) {
        let base = Self.env("NATIVE_AUTH_TURNSTILE_PAGE") ?? "http://127.0.0.1:57462/turnstile.html"
        turnstilePage = URL(string: "\(base)?sitekey=\(sitekey)")
        log("turnstile.open", ["sitekey": sitekey, "page_host": turnstilePage?.host() ?? ""])
    }

    func turnstileEvent(_ event: String, token: String?, detail: String?) async {
        turnstilePage = nil
        log("turnstile.\(event)", ["token_received": String(token != nil), "detail": detail ?? ""])
        guard event == "token", let token, let client else { return }
        if let email = pendingRecoveryEmail {
            pendingRecoveryEmail = nil
            return await requestRecovery(email, captchaToken: token)
        }
        do {
            _ = try await client.startGuest(captchaToken: token)
            let me = try await client.request("GET", "/me")
            log("guest.start", ["result": "ok", "me_status": String(me.status)])
        } catch let ArgusAuthError.rejected(status, code) {
            log("guest.start", ["result": "rejected", "status": String(status), "code": code ?? ""])
        } catch {
            log("guest.start", ["result": "error", "type": String(describing: type(of: error))])
        }
    }

    func cancelTurnstile() {
        guard turnstilePage != nil else { return }
        turnstilePage = nil
        pendingRecoveryEmail = nil
        log("turnstile.cancelled", ["request_sent": "false"])
    }

    func requestRecovery(_ email: String, captchaToken: String) async {
        do {
            try await client?.requestRecovery(email: email, captchaToken: captchaToken)
            log("recovery.requested", ["result": "ok"])
        } catch {
            log("recovery.requested", ["result": "error", "type": String(describing: error).prefix(80).description])
        }
    }

    func handleCallback(_ url: URL) async {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let errorCode = items.first { $0.name == "error_code" }?.value ?? ""
        log("callback.received", [
            "scheme": url.scheme ?? "",
            "host": url.host() ?? "",
            "has_code": String(items.contains { $0.name == "code" }),
            "code_kind": items.first { $0.name == "code" }.map {
                $0.value == "00000000-0000-0000-0000-000000000000" ? "forged" : "issued"
            } ?? "none",
            "error_code": errorCode,
        ])
        guard let client else { return }
        do {
            _ = try await client.completeCallback(url)
            let me = try await client.request("GET", "/me")
            log("callback.completed", ["result": "session", "me_status": String(me.status)])
        } catch let AuthError.api(_, code, _, _) {
            log("callback.completed", ["result": "refused", "code": code.rawValue])
        } catch {
            log("callback.completed", ["result": "refused", "type": String(describing: error).prefix(80).description])
        }
    }
}

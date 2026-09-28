import ArgusNativeAuth
import Foundation
import XCTest

/// Lane stack settings. xcodebuild forwards TEST_RUNNER_<NAME> as <NAME>.
enum Env {
    static func value(_ name: String) -> String {
        guard let value = ProcessInfo.processInfo.environment[name], !value.isEmpty else {
            fatalError("missing \(name); run probes/native-auth/ios/run-simulator-tests.sh")
        }
        return value
    }

    static let stack = Stack(
        argusAPI: URL(string: value("NATIVE_AUTH_ARGUS_API"))!,
        supabaseURL: URL(string: value("NATIVE_AUTH_SUPABASE_URL"))!,
        anonKey: value("NATIVE_AUTH_ANON_KEY")
    )
    static let adapter = URL(string: value("NATIVE_AUTH_ADAPTER"))!
    static let serviceKey = value("NATIVE_AUTH_SERVICE_ROLE_KEY")
    static let mailpit = URL(string: value("NATIVE_AUTH_MAILPIT_URL"))!
    static let callback = URL(string: "argusnativeproof://auth-callback")!
    static let captcha = "native-proof-local-captcha"
    static let runID = UUID().uuidString.prefix(8).lowercased()
    static let net = (Int.random(in: 1...250), Int.random(in: 1...250))
}

struct Identity {
    let email: String
    let password: String
}

enum Fixture {
    private static var counter = 0

    static func deviceIP() -> String {
        counter += 1
        return "10.\(Env.net.0).\(Env.net.1).\(counter)"
    }

    static func client(
        _ name: String,
        transport: HandoffTransport = .scopedCookies,
        argusBase: URL? = nil,
        deviceIP: String? = nil
    ) -> ArgusNativeClient {
        let client = ArgusNativeClient(
            stack: Env.stack,
            argusBase: argusBase,
            keychainService: "argus.native.proof.\(Env.runID).\(name)",
            handoffTransport: transport,
            callback: Env.callback,
            deviceIP: deviceIP ?? Self.deviceIP()
        )
        return client
    }

    static func email(_ label: String) -> String {
        "native-ios-\(label)-\(Env.runID)@proof.argus.local"
    }

    static func password() -> String {
        UUID().uuidString + UUID().uuidString.prefix(6)
    }

    static func allowlist(_ email: String) async throws {
        var request = URLRequest(url: Env.stack.supabaseURL.appending(path: "rest/v1/private_alpha_allowlist"))
        request.httpMethod = "POST"
        request.setValue(Env.serviceKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(Env.serviceKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("resolution=ignore-duplicates", forHTTPHeaderField: "Prefer")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["email": email])
        let (_, response) = try await URLSession.shared.data(for: request)
        XCTAssertLessThan((response as! HTTPURLResponse).statusCode, 300)
    }

    static func user(_ label: String) async throws -> Identity {
        let identity = Identity(email: email(label), password: password())
        var request = URLRequest(url: Env.stack.supabaseURL.appending(path: "auth/v1/admin/users"))
        request.httpMethod = "POST"
        request.setValue(Env.serviceKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(Env.serviceKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(
            withJSONObject: ["email": identity.email, "password": identity.password, "email_confirm": true]
        )
        let (_, response) = try await URLSession.shared.data(for: request)
        XCTAssertEqual((response as! HTTPURLResponse).statusCode, 200)
        try await allowlist(identity.email)
        return identity
    }

    /// Signs another account in through the same Argus process. Argus's shared
    /// server-side Supabase client refreshes only the last session it signed in
    /// (finding A14), so this keeps that timer off the session under test.
    static func moveServerRefreshTimer() async throws {
        let decoy = try await user("decoy-\(UUID().uuidString.prefix(4).lowercased())")
        _ = try await client("decoy").signIn(email: decoy.email, password: decoy.password, captchaToken: Env.captcha)
    }

    static func rawRefresh(_ refreshToken: String) async throws -> Int {
        var request = URLRequest(
            url: Env.stack.supabaseURL.appending(path: "auth/v1/token").appending(queryItems: [.init(name: "grant_type", value: "refresh_token")])
        )
        request.httpMethod = "POST"
        request.setValue(Env.stack.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["refresh_token": refreshToken])
        let (_, response) = try await URLSession.shared.data(for: request)
        return (response as! HTTPURLResponse).statusCode
    }

    static func latestAuthLink(to email: String, after: Date) async throws -> URL {
        for _ in 0..<40 {
            let search = Env.mailpit.appending(path: "api/v1/search").appending(queryItems: [.init(name: "query", value: "to:\(email)")])
            let (data, _) = try await URLSession.shared.data(from: search)
            let listing = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            for message in listing?["messages"] as? [[String: Any]] ?? [] {
                guard let created = message["Created"] as? String,
                      let date = ISO8601DateFormatter.fractional.date(from: created),
                      date.addingTimeInterval(1) >= after,
                      let id = message["ID"] as? String
                else { continue }
                let (full, _) = try await URLSession.shared.data(from: Env.mailpit.appending(path: "api/v1/message/\(id)"))
                let text = (try JSONSerialization.jsonObject(with: full) as? [String: Any])?["Text"] as? String ?? ""
                if let range = text.range(of: #"https?://[^\s"'<>]+/auth/v1/verify[^\s"'<>]+"#, options: .regularExpression) {
                    return URL(string: String(text[range]).replacingOccurrences(of: "&amp;", with: "&"))!
                }
            }
            try await Task.sleep(for: .milliseconds(500))
        }
        throw URLError(.timedOut)
    }

    /// Opens the email link the way a mail client would and returns where
    /// Supabase sends the user, without following that redirect.
    static func callbackURL(for link: URL) async throws -> URL {
        let session = URLSession(configuration: .ephemeral, delegate: NoRedirect(), delegateQueue: nil)
        let (_, response) = try await session.data(from: link)
        let location = (response as! HTTPURLResponse).value(forHTTPHeaderField: "Location") ?? ""
        return URL(string: location)!
    }
}

final class NoRedirect: NSObject, URLSessionTaskDelegate {
    func urlSession(
        _ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest
    ) async -> URLRequest? { nil }
}

extension ISO8601DateFormatter {
    static let fractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}

/// One line per scenario, parsed from the xcodebuild log into evidence JSON.
/// Observed values are statuses, codes, and booleans only.
func probeResult(
    _ id: String,
    area: String,
    scenario: String,
    path: String = "unchanged-argus",
    level: Int = 4,
    expected: String,
    observed: [String: Any],
    ok: Bool,
    note: String = "",
    file: StaticString = #filePath,
    line: UInt = #line
) {
    let entry: [String: Any] = [
        "id": id, "area": area, "scenario": scenario, "path": path, "evidence_level": level,
        "expected": expected, "observed": observed, "verdict": ok ? "pass" : "fail", "note": note,
    ]
    let data = try! JSONSerialization.data(withJSONObject: entry, options: [.sortedKeys])
    print("NATIVE_PROBE_RESULT \(String(decoding: data, as: UTF8.self))")
    XCTAssertTrue(ok, "\(id) \(scenario): \(observed)", file: file, line: line)
}

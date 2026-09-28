import Foundation

/// How the guest handoff secret travels between app and Argus.
public enum HandoffTransport: Sendable {
    /// Unchanged Argus: the app keeps only the two handoff cookies, in the
    /// Keychain, and replays them as a Cookie header on /api/v1/auth paths.
    case scopedCookies
    /// Proposal E3, served by the synthetic adapter: JSON body in, headers out.
    case header
}

public struct StoredHandoff: Codable, Equatable, Sendable {
    public let id: String
    public let secret: String
}

/// The guest handoff credential. Single purpose: it is sent only to
/// /api/v1/auth routes and deleted when Argus says the handoff is finished.
public struct HandoffStore: Sendable {
    static let key = "guest-handoff"
    static let cookieNames = ["argus-guest-handoff", "argus-guest-handoff-id"]
    let keychain: KeychainStore
    public let transport: HandoffTransport

    public init(keychain: KeychainStore, transport: HandoffTransport) {
        self.keychain = keychain
        self.transport = transport
    }

    public var current: StoredHandoff? {
        (try? keychain.retrieve(key: Self.key)).flatMap { try? JSONDecoder().decode(StoredHandoff.self, from: $0) }
    }

    public func headers(forPath path: String) -> [String: String] {
        guard path.hasPrefix("/auth/") else { return [:] }
        switch transport {
        case .scopedCookies:
            guard let handoff = current else { return [:] }
            return ["Cookie": "argus-guest-handoff=\(handoff.secret); argus-guest-handoff-id=\(handoff.id)"]
        case .header:
            var headers = ["Argus-Guest-Handoff-Transport": "header"]
            if let handoff = current {
                headers["Argus-Guest-Handoff-Id"] = handoff.id
                headers["Argus-Guest-Handoff-Secret"] = handoff.secret
            }
            return headers
        }
    }

    /// Applies what a response says about the handoff. Ignores every other cookie.
    public func absorb(_ response: APIResponse) throws {
        switch transport {
        case .scopedCookies:
            let cookies = response.setCookies.filter { Self.cookieNames.contains($0.name) }
            guard !cookies.isEmpty else { return }
            let expired = cookies.contains { ($0.expiresDate ?? .distantFuture) <= Date() || $0.value.isEmpty }
            if expired { return try keychain.remove(key: Self.key) }
            let secret = cookies.first { $0.name == "argus-guest-handoff" }?.value
            let id = cookies.first { $0.name == "argus-guest-handoff-id" }?.value
            if let secret, let id { try save(StoredHandoff(id: id, secret: secret)) }
        case .header:
            if response.headers["argus-guest-handoff-state"] == "cleared" {
                return try keychain.remove(key: Self.key)
            }
            if let secret = response.body["handoff_secret"] as? String,
               let id = response.body["handoff_id"] as? String
            {
                try save(StoredHandoff(id: id, secret: secret))
            }
        }
    }

    public func clear() throws {
        try keychain.remove(key: Self.key)
    }

    private func save(_ handoff: StoredHandoff) throws {
        try keychain.store(key: Self.key, value: JSONEncoder().encode(handoff))
    }
}

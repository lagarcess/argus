import Foundation

/// Safe, bounded failures. Never includes server prose, passwords, tokens or SDK errors.
public enum SessionFailure: Error, Equatable, Sendable {
    case busy, invalidConfiguration, invalidResponse, unauthorized, unavailable
    case storageUnavailable, pendingSignOut, unsupportedAnonymousTransfer, staleOperation
    case rejected(status: Int, code: String?)
}

public struct SessionProfile: Equatable, Sendable, Decodable {
    public let id: String
    public let email: String?
    public let displayName: String?
    public let language: String?
    public let currency: String?
    public let currencyOverride: String?
    init(id: String, email: String?, displayName: String?, language: String?, currency: String? = nil, currencyOverride: String? = nil) {
        self.id = id; self.email = email; self.displayName = displayName; self.language = language
        self.currency = currency; self.currencyOverride = currencyOverride
    }
    enum CodingKeys: String, CodingKey { case id, email, language; case displayName = "display_name"; case currency; case currencyOverride = "currency_override" }
}

public struct SessionSnapshot: Equatable, Sendable {
    public enum Phase: Equatable, Sendable {
        case signedOut, authenticated, signOutPending, unsupportedAnonymousSession
    }
    public let phase: Phase
    public let profile: SessionProfile?
    public let revision: UInt64
    /// A snapshot names an identity; only `SessionController` can make one usable for requests.
    public init(phase: Phase, profile: SessionProfile?, revision: UInt64) {
        self.phase = phase; self.profile = profile; self.revision = revision
    }
}

public enum SignupOutcome: Equatable, Sendable {
    case confirmationRequired
    case authenticated(SessionSnapshot)
}

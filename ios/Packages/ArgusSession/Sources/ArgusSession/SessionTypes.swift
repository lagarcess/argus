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
    enum CodingKeys: String, CodingKey { case id, email, language; case displayName = "display_name" }
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

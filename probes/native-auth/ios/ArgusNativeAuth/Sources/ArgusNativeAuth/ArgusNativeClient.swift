import Auth
import Foundation

public enum ArgusAuthError: Error, Equatable {
    case staleAccount
    case signedOut
    case rejected(status: Int, code: String?)
}

public struct SignInOutcome: Sendable {
    public let userID: String
    public let claimedConversationID: String?
}

/// Argus owns entry (captcha, limits, allowlist, guest claim). The Supabase SDK
/// owns the session afterwards: storage, refresh, revoke, recovery callbacks.
public final class ArgusNativeClient: Sendable {
    public let auth: AuthClient
    public let transport: BearerTransport
    public let handoffs: HandoffStore
    public let boundary = AccountBoundary()
    public let keychain: KeychainStore

    public init(
        stack: Stack,
        argusBase: URL? = nil,
        keychainService: String,
        handoffTransport: HandoffTransport = .scopedCookies,
        callback: URL,
        deviceIP: String? = nil,
        logger: (any SupabaseLogger)? = nil
    ) {
        keychain = KeychainStore(service: keychainService)
        auth = AuthClient(
            url: stack.supabaseURL.appending(path: "auth/v1"),
            headers: ["apikey": stack.anonKey],
            flowType: .pkce,
            redirectToURL: callback,
            localStorage: keychain,
            logger: logger,
            autoRefreshToken: false
        )
        transport = BearerTransport(base: argusBase ?? stack.argusAPI, deviceIP: deviceIP)
        handoffs = HandoffStore(keychain: keychain, transport: handoffTransport)
    }

    // MARK: Entry, always through Argus

    public func startGuest(captchaToken: String) async throws -> String {
        let bearer = auth.currentSession?.accessToken
        let response = try await authCall("/auth/guest", bearer: bearer, json: ["captcha_token": captchaToken, "language": "en"])
        guard response.status == 200 else { throw rejection(response) }
        if response.body["reused"] as? Bool != true { try await adopt(response) }
        return ((response.body["user"] as? [String: Any])?["id"] as? String) ?? ""
    }

    public func signIn(email: String, password: String, captchaToken: String) async throws -> SignInOutcome {
        let response = try await authCall(
            "/auth/login",
            json: ["email": email, "password": password, "captcha_token": captchaToken]
        )
        guard response.status == 200 else {
            if response.body["session"] != nil {
                // Proposal P3: a session created beside a handoff problem is revoked, not orphaned.
                try await adopt(response)
                try await auth.signOut(scope: .local)
            }
            throw rejection(response)
        }
        try await adopt(response)
        let claim = response.body["guest_claim"] as? [String: Any]
        return SignInOutcome(
            userID: ((response.body["user"] as? [String: Any])?["id"] as? String) ?? "",
            claimedConversationID: claim?["conversation_id"] as? String
        )
    }

    public func createHandoff(destinationEmail: String, conversationID: String, kind: String = "existing_account") async throws {
        let bearer = try await auth.session.accessToken
        let response = try await authCall(
            "/auth/guest/handoffs",
            bearer: bearer,
            json: ["handoff_kind": kind, "destination_email": destinationEmail, "source_conversation_id": conversationID]
        )
        guard response.status == 201 else { throw rejection(response) }
    }

    public func signUpFromGuest(email: String, password: String, captchaToken: String) async throws -> APIResponse {
        let bearer = try await auth.session.accessToken
        let response = try await authCall(
            "/auth/guest/signup",
            bearer: bearer,
            json: ["email": email, "password": password, "captcha_token": captchaToken, "language": "en"]
        )
        guard response.status == 200 else { throw rejection(response) }
        if response.body["session"] is [String: Any] { try await adopt(response) }
        return response
    }

    // MARK: Account-scoped requests

    public func request(
        _ method: String,
        _ path: String,
        json: [String: any Sendable]? = nil,
        cacheKey: String? = nil,
        onStarted: (@Sendable () -> Void)? = nil
    ) async throws -> APIResponse {
        let started = await boundary.begin()
        var response = try await transport.send(method, path, bearer: try await accessToken(), json: json, onStarted: onStarted)
        if response.status == 401 {
            do {
                _ = try await auth.refreshSession()
            } catch {
                await boundary.end()
                throw ArgusAuthError.signedOut
            }
            response = try await transport.send(method, path, bearer: try await accessToken(), json: json)
            if response.status == 401 {
                try await signOut()
                throw ArgusAuthError.signedOut
            }
        }
        return try await boundary.deliver(response, startedIn: started, cacheKey: cacheKey)
    }

    // MARK: Exit

    /// Revokes this device's session at Supabase and clears local state.
    public func signOut() async throws {
        await boundary.end()
        try handoffs.clear()
        try await auth.signOut(scope: .local)
    }

    /// Anti-pattern kept for comparison: forgets tokens without revoking them.
    public func forgetLocally() async {
        await boundary.end()
        keychain.removeAll()
    }

    // MARK: Recovery

    public func requestRecovery(email: String, captchaToken: String? = nil) async throws {
        try await auth.resetPasswordForEmail(email, captchaToken: captchaToken)
    }

    /// Handles an app callback URL. Throws for invalid, repeated, expired, or foreign codes.
    public func completeCallback(_ url: URL) async throws -> Session {
        let session = try await auth.session(from: url)
        await boundary.end()
        return session
    }

    // MARK: Internals

    private func accessToken() async throws -> String {
        do {
            return try await auth.session.accessToken
        } catch {
            await boundary.end()
            throw ArgusAuthError.signedOut
        }
    }

    private func authCall(_ path: String, bearer: String? = nil, json: [String: any Sendable]) async throws -> APIResponse {
        let response = try await transport.send(
            "POST", path, bearer: bearer, json: json, headers: handoffs.headers(forPath: path)
        )
        try handoffs.absorb(response)
        return response
    }

    private func adopt(_ response: APIResponse) async throws {
        guard let session = response.body["session"] as? [String: Any],
              let access = session["access_token"] as? String,
              let refresh = session["refresh_token"] as? String
        else { return }
        await boundary.end()
        try await auth.setSession(accessToken: access, refreshToken: refresh)
    }

    private func rejection(_ response: APIResponse) -> ArgusAuthError {
        .rejected(status: response.status, code: response.problemCode)
    }
}

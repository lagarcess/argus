import Auth
import Foundation

/// The sole native session owner. Product identity comes from Argus /me, not a
/// decoded JWT or a parallel profile cache. Account API values are transported without client financial rules.
public actor SessionController {
    private let configuration: SessionConfiguration
    private let vault: CredentialVault
    private let transport: SessionTransport
    private var auth: AuthClient?
    private var mutating = false
    private var state = SessionSnapshot(phase: .signedOut, profile: nil, revision: 0)

    public init(configuration: SessionConfiguration) throws {
        self.configuration = configuration
        self.vault = CredentialVault(backing: DeviceKeychain(service: configuration.keychainService), prefix: configuration.storagePrefix)
        self.transport = SessionTransport()
    }
    init(configuration: SessionConfiguration, storage: any AuthLocalStorage, fetch: @escaping AuthClient.FetchHandler) throws {
        self.configuration = configuration
        self.vault = CredentialVault(backing: storage, prefix: configuration.storagePrefix)
        self.transport = SessionTransport(fetch: fetch)
    }
    public func snapshot() -> SessionSnapshot { state }

    public func restore() async throws -> SessionSnapshot {
        try beginMutation(); defer { mutating = false }
        if try vault.pending() != nil {
            setState(.signOutPending)
            return try await performPendingRevoke()
        }
        guard let existing = try vault.session() else { endAccountEpoch(as: .signedOut); return state }
        if existing.user.isAnonymous { setState(.unsupportedAnonymousSession); return state }
        return try await loadProfile(using: activeAuth(), epoch: vault.epoch())
    }

    public func login(email: String, password: String, captchaToken: String) async throws -> SessionSnapshot {
        try beginMutation(); defer { mutating = false }
        try requireEntry()
        let response = try await entry(path: "auth/login", body: ["email": email, "password": password, "captcha_token": captchaToken])
        guard let credentials = response.session else { throw SessionFailure.invalidResponse }
        return try await adopt(credentials)
    }

    public func signup(email: String, password: String, captchaToken: String, language: String,
                       displayName: String? = nil) async throws -> SignupOutcome {
        try beginMutation(); defer { mutating = false }
        try requireEntry()
        var body = ["email": email, "password": password, "captcha_token": captchaToken, "language": language]
        if let displayName { body["display_name"] = displayName }
        let response = try await entry(path: "auth/signup", body: body)
        guard let credentials = response.session else { return .confirmationRequired }
        return .authenticated(try await adopt(credentials))
    }

    /// Native Apple or Google sign-in. The provider's ID token and the raw nonce go to
    /// Supabase Auth's id_token grant on an isolated in-memory client; the issued tokens
    /// then take the same journaled adoption path as email sign-in (pending journal,
    /// setSession, then the canonical /me profile). If Argus refuses the new session
    /// (for example the private-alpha allowlist at /me), it is revoked before returning.
    public func signIn(with credential: IdentityTokenCredential) async throws -> SessionSnapshot {
        try beginMutation(); defer { mutating = false }
        try requireEntry()
        guard credential.wellFormed else { throw SessionFailure.invalidResponse }
        let exchange = makeAuth(storage: ExchangeStorage(), fetch: transport.sdkFetch(origin: configuration.supabaseURL))
        let issued: Session
        do {
            issued = try await exchange.signInWithIdToken(credentials: OpenIDConnectCredentials(
                provider: credential.provider == .apple ? .apple : .google, idToken: credential.idToken,
                accessToken: credential.accessToken, nonce: credential.nonce.raw))
        } catch {
            if case let AuthError.api(_, code, _, response) = error {
                if response.statusCode >= 500 { throw SessionFailure.unavailable }
                throw SessionFailure.rejected(status: response.statusCode, code: bounded(code.rawValue))
            }
            throw safe(error)
        }
        guard !issued.user.isAnonymous else { throw SessionFailure.unsupportedAnonymousTransfer }
        do {
            return try await adopt(Credentials(accessToken: issued.accessToken, refreshToken: issued.refreshToken))
        } catch {
            // adopt() has journaled the issued session as pending; revoke it now so a
            // refused provider account doesn't leave the person on the sign-out screen.
            _ = try? await performPendingRevoke()
            throw error
        }
    }

    public func profile() async throws -> SessionSnapshot {
        guard !mutating else { throw SessionFailure.busy }
        if try vault.pending() != nil { throw SessionFailure.pendingSignOut }
        guard let session = try vault.session() else { throw SessionFailure.unauthorized }
        guard !session.user.isAnonymous else { throw SessionFailure.unsupportedAnonymousTransfer }
        return try await loadProfile(using: activeAuth(), epoch: vault.epoch())
    }

    public func setPrimaryCurrency(_ currency: String, expectedIdentity: SessionSnapshot) async throws -> SessionSnapshot {
        guard state.phase == .authenticated, state.revision == expectedIdentity.revision,
              state.profile?.id == expectedIdentity.profile?.id else { throw SessionFailure.staleOperation }
        try beginMutation(); defer { mutating = false }
        if try vault.pending() != nil { throw SessionFailure.pendingSignOut }
        let epoch = vault.epoch()
        var request = URLRequest(url: configuration.argusAPIURL.appending(path: "api/v1/me"))
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoded(["currency_override": currency])
        _ = try await authenticatedResponse(using: activeAuth(), epoch: epoch, request: request)
        return try await loadProfile(using: activeAuth(), epoch: epoch)
    }

    public func signOut() async throws -> SessionSnapshot {
        try beginMutation(); defer { mutating = false }
        if try vault.pending() == nil {
            guard let current = try vault.session() else { endAccountEpoch(as: .signedOut); return state }
            guard !current.user.isAnonymous else { throw SessionFailure.unsupportedAnonymousTransfer }
        }
        try suspendUsableSession()
        return try await performPendingRevoke()
    }

    public func retryPendingSignOut() async throws -> SessionSnapshot {
        try beginMutation(); defer { mutating = false }
        guard try vault.pending() != nil else { return state }
        try suspendUsableSession()
        return try await performPendingRevoke()
    }

    private func beginMutation() throws {
        guard !mutating else { throw SessionFailure.busy }
        mutating = true
    }
    private func requireEntry() throws {
        if try vault.pending() != nil { setState(.signOutPending); throw SessionFailure.pendingSignOut }
        if let existing = try vault.session() {
            if existing.user.isAnonymous {
                setState(.unsupportedAnonymousSession)
                throw SessionFailure.unsupportedAnonymousTransfer
            }
            throw SessionFailure.rejected(status: 409, code: "already_authenticated")
        }
        try vault.preflight()
    }
    private func activeAuth() -> AuthClient {
        if let auth { return auth }
        let client = makeAuth(storage: EpochStorage(vault: vault, epoch: vault.epoch()), fetch: transport.sdkFetch(origin: configuration.supabaseURL))
        auth = client
        return client
    }
    private func makeAuth(storage: any AuthLocalStorage, fetch: @escaping AuthClient.FetchHandler) -> AuthClient {
        AuthClient(url: configuration.supabaseURL.appending(path: "auth/v1"),
                   headers: ["apikey": configuration.publicAnonKey], storageKey: "argus.session",
                   localStorage: storage, logger: nil, fetch: fetch, autoRefreshToken: false)
    }
    private func setState(_ phase: SessionSnapshot.Phase, profile: SessionProfile? = nil) {
        state = .init(phase: phase, profile: profile, revision: vault.epoch())
    }
    private func endAccountEpoch(as phase: SessionSnapshot.Phase) {
        vault.retire()
        auth = nil
        setState(phase)
    }
    private struct EntryResponse: Decodable {
        let session: Credentials?
    }
    private struct Credentials: Decodable {
        let accessToken: String
        let refreshToken: String
        enum CodingKeys: String, CodingKey { case accessToken = "access_token", refreshToken = "refresh_token" }
    }
    private func entry(path: String, body: [String: String]) async throws -> EntryResponse {
        do {
            var request = URLRequest(url: configuration.argusAPIURL.appending(path: "api/v1/" + path))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
            let (data, response) = try await transport.send(request, origin: configuration.argusAPIURL)
            guard (200..<300).contains(response.statusCode) else { throw problem(data, status: response.statusCode) }
            return try JSONDecoder().decode(EntryResponse.self, from: data)
        } catch { throw safe(error) }
    }
    private func adopt(_ credentials: Credentials) async throws -> SessionSnapshot {
        guard !credentials.accessToken.isEmpty, !credentials.refreshToken.isEmpty else { throw SessionFailure.invalidResponse }
        // Journal before SDK adoption: a crash or swallowed persistence error must not
        // leave an issued server session invisible to the next launch.
        setState(.signOutPending)
        try vault.savePending(.init(accessToken: credentials.accessToken, refreshToken: credentials.refreshToken))
        endAccountEpoch(as: .signOutPending)
        let epoch = vault.epoch()
        let client = activeAuth()
        do {
            let session = try await client.setSession(accessToken: credentials.accessToken, refreshToken: credentials.refreshToken)
            try vault.check(epoch)
            guard let stored = try vault.session(), stored.refreshToken == session.refreshToken else { throw SessionFailure.storageUnavailable }
            guard !session.user.isAnonymous else { throw SessionFailure.unsupportedAnonymousTransfer }
            let result = try await loadProfile(using: client, epoch: epoch)
            try vault.removePending()
            return result
        } catch {
            try suspendUsableSession()
            throw safe(error)
        }
    }

    private func loadProfile(using client: AuthClient, epoch: UInt64) async throws -> SessionSnapshot {
        let request = URLRequest(url: configuration.argusAPIURL.appending(path: "api/v1/me"))
        let result = try await authenticatedResponse(using: client, epoch: epoch, request: request)
        do {
            struct ProfileEnvelope: Decodable { let user: SessionProfile }
            let profile = try JSONDecoder().decode(ProfileEnvelope.self, from: result.0).user
            guard UUID(uuidString: profile.id) == (try vault.session())?.user.id else {
                try suspendUsableSession()
                throw SessionFailure.invalidResponse
            }
            try vault.check(epoch)
            setState(.authenticated, profile: profile)
            return state
        } catch { throw safe(error) }
    }
    /// Shared authenticated transport for /me and financial records. SDK owns
    /// refresh coalescing; this layer permits only one 401 refresh/retry.
    private func authenticatedResponse(using client: AuthClient, epoch: UInt64,
                                       request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        var retiring = false
        do {
            try vault.check(epoch)
            let session = try await client.session
            try vault.check(epoch)
            guard !session.user.isAnonymous else { throw SessionFailure.unsupportedAnonymousTransfer }
            var authorized = request
            authorized.setValue("Bearer " + session.accessToken, forHTTPHeaderField: "Authorization")
            var result = try await transport.send(authorized, origin: configuration.argusAPIURL)
            try vault.check(epoch)
            if result.1.statusCode == 401 {
                let refreshed = try await client.refreshSession()
                try vault.check(epoch)
                authorized.setValue("Bearer " + refreshed.accessToken, forHTTPHeaderField: "Authorization")
                result = try await transport.send(authorized, origin: configuration.argusAPIURL)
                try vault.check(epoch)
            }
            guard result.1.statusCode != 401 else {
                retiring = true
                try suspendUsableSession()
                throw SessionFailure.unauthorized
            }
            guard (200..<300).contains(result.1.statusCode) else { throw problem(result.0, status: result.1.statusCode) }
            return result
        } catch {
            if vault.epoch() != epoch {
                if retiring { throw safe(error) }
                throw SessionFailure.staleOperation
            }
            do { try vault.check(epoch) }
            catch { try suspendUsableSession(); throw SessionFailure.storageUnavailable }
            if (error as? AuthError) == .sessionMissing {
                endAccountEpoch(as: .signedOut)
                try vault.removeSession()
                throw SessionFailure.unauthorized
            }
            if case let AuthError.api(_, _, _, response) = error,
               [400, 401, 403].contains(response.statusCode) {
                try suspendUsableSession()
                throw SessionFailure.unauthorized
            }
            throw safe(error)
        }
    }
    private func suspendUsableSession() throws {
        // Invalidate delivery and SDK writes before journal I/O can fail. Actual
        // credential removal still waits for a successful durable pending write.
        endAccountEpoch(as: .signOutPending)
        if let pending = try vault.pending() {
            // A previous failed write may have left this journal only in memory.
            try vault.savePending(pending)
        } else if let current = try vault.session() {
            try vault.savePending(.init(accessToken: current.accessToken, refreshToken: current.refreshToken))
        }
        try vault.removeSession()
    }

    private func performPendingRevoke() async throws -> SessionSnapshot {
        guard let pending = try vault.pending() else { endAccountEpoch(as: .signedOut); return state }
        setState(.signOutPending)
        let storage = RevocationStorage(vault: vault)
        let receipt = RevokeReceipt()
        let origin = configuration.supabaseURL
        let transport = self.transport
        let client = makeAuth(storage: storage, fetch: { request in
            let (data, response) = try await transport.send(request, origin: origin)
            receipt.observe(request, response: response)
            return (data, response)
        })
        do {
            // Refresh first: SDK signOut silently accepts an expired-JWT 401, which
            // does not prove the refresh session was revoked. Rotations persist first.
            _ = try await client.refreshSession(refreshToken: pending.refreshToken)
            try storage.check()
            try await client.signOut(scope: .local)
            try storage.check()
            guard receipt.confirmed else { return state }
        } catch {
            try storage.check()
            guard (error as? AuthError) == .sessionMissing else {
                if (error as? SessionFailure) == .storageUnavailable { throw SessionFailure.storageUnavailable }
                return state
            }
        }
        // Clear residual SDK state before the pending marker, including interrupted
        // local cleanup from an earlier launch.
        try vault.removeSession()
        try vault.removePending()
        endAccountEpoch(as: .signedOut)
        return state
    }
    private func problem(_ data: Data, status: Int) -> SessionFailure {
        if status >= 500 { return .unavailable }
        struct Problem: Decodable { let code: String? }
        let raw = (try? JSONDecoder().decode(Problem.self, from: data))?.code
        return .rejected(status: status, code: raw.flatMap(bounded))
    }
    /// Only a bounded identifier reaches UI, never arbitrary server detail.
    private func bounded(_ value: String) -> String? {
        value.count <= 80 && value.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_") } ? value : nil
    }
    private func safe(_ error: any Error) -> SessionFailure {
        if let failure = error as? SessionFailure { return failure }
        if error is DecodingError { return .invalidResponse }
        if (error as? AuthError) == .sessionMissing { return .unauthorized }
        return .unavailable
    }
}


extension SessionController {
    public func financialAccounts(expectedIdentity: SessionSnapshot) async throws -> [FinancialAccount] {
        struct Envelope: Decodable { let accounts: [FinancialAccount] }
        let data = try await financialRequest(expectedIdentity: expectedIdentity)
        do { return try JSONDecoder().decode(Envelope.self, from: data).accounts }
        catch { throw SessionFailure.invalidResponse }
    }

    public func financialAccount(id: UUID, expectedIdentity: SessionSnapshot) async throws -> FinancialAccount {
        try decodeAccount(await financialRequest(path: "/" + id.uuidString, expectedIdentity: expectedIdentity))
    }

    public func createFinancialAccount(_ request: CreateFinancialAccountRequest,
                                       expectedIdentity: SessionSnapshot) async throws -> FinancialAccount {
        try decodeAccount(await financialRequest(method: "POST", body: encoded(request),
            key: request.idempotencyKey.uuidString, expectedIdentity: expectedIdentity))
    }

    public func updateFinancialAccount(id: UUID, request: EditFinancialAccountRequest,
                                       expectedIdentity: SessionSnapshot) async throws -> FinancialAccount {
        try decodeAccount(await financialRequest(path: "/" + id.uuidString, method: "PATCH",
            body: encoded(request), expectedIdentity: expectedIdentity))
    }

    public func writeOpening(id: UUID, request: WriteOpeningRequest, key: UUID? = nil,
                             expectedIdentity: SessionSnapshot) async throws -> FinancialAccount {
        try decodeAccount(await financialRequest(path: "/" + id.uuidString + "/opening", method: "PUT",
            body: encoded(request), key: key?.uuidString, expectedIdentity: expectedIdentity))
    }

    func encoded(_ value: some Encodable) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        return try encoder.encode(value)
    }
    private func decodeAccount(_ data: Data) throws -> FinancialAccount {
        do { return try JSONDecoder().decode(FinancialAccount.self, from: data) }
        catch { throw SessionFailure.invalidResponse }
    }
    func financialRequest(route: String = "financial-accounts", path: String = "", method: String = "GET", body: Data? = nil,
                                  key: String? = nil, query: [URLQueryItem] = [], expectedIdentity: SessionSnapshot) async throws -> Data {
        guard expectedIdentity.phase == .authenticated, expectedIdentity.profile != nil else { throw SessionFailure.unauthorized }
        guard state.phase == .authenticated, state.revision == expectedIdentity.revision,
              state.profile?.id == expectedIdentity.profile?.id else { throw SessionFailure.staleOperation }
        guard !mutating else { throw SessionFailure.busy }
        if try vault.pending() != nil { throw SessionFailure.pendingSignOut }
        let epoch = vault.epoch()
        try vault.check(epoch)
        var components = URLComponents(url: configuration.argusAPIURL.appending(path: "api/v1/" + route + path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var request = URLRequest(url: components.url!)
        request.httpMethod = method
        request.httpBody = body
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let key { request.setValue(key, forHTTPHeaderField: "Idempotency-Key") }
        return try await authenticatedResponse(using: activeAuth(), epoch: epoch, request: request).0
    }
}

import ArgusNativeAuth
import Auth
import Foundation
import Security
import XCTest

final class SessionScenarioTests: XCTestCase {
    func testI1SignInPersistsAcrossRelaunchInDeviceOnlyKeychain() async throws {
        let alice = try await Fixture.user("i1")
        let ip = Fixture.deviceIP()
        let first = Fixture.client("i1", deviceIP: ip)
        _ = try await first.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let relaunched = Fixture.client("i1", deviceIP: ip)
        let me = try await relaunched.request("GET", "/me")
        let classes = first.keychain.accessibilities()
        let deviceOnly = !classes.isEmpty && classes.allSatisfy { $0 == (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String) }
        probeResult(
            "I1", area: "sign-in",
            scenario: "Sign in through Argus, hand the session to supabase-swift, relaunch with a new client",
            expected: "Relaunched client restores the session from Keychain and reaches GET /me; item is device-only",
            observed: [
                "relaunch_has_session": relaunched.auth.currentSession != nil,
                "me_status": me.status,
                "keychain_items": classes.count,
                "keychain_accessibility_this_device_only": deviceOnly,
            ],
            ok: me.status == 200 && deviceOnly,
            note: "Storage is the probe's KeychainStore. The SDK default KeychainLocalStorage uses AfterFirstUnlock, which migrates through backups."
        )
        first.keychain.removeAll()
    }

    func testI2BearerOnlyTransportNeverHoldsCookies() async throws {
        let alice = try await Fixture.user("i2")
        let client = Fixture.client("i2")
        _ = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let noBearer = try await client.transport.send("GET", "/me")
        let shared = HTTPCookieStorage.shared.cookies(for: Env.stack.argusAPI) ?? []
        probeResult(
            "I2", area: "cookie-hazard",
            scenario: "Argus sets sb-* cookies on sign-in; the app's transport refuses them",
            expected: "No Argus cookie stored anywhere; a request without the bearer is 401",
            observed: ["shared_cookie_names": shared.map(\.name).sorted(), "no_bearer_status": noBearer.status],
            ok: shared.isEmpty && noBearer.status == 401,
            note: "Contrast with HTTP probe A11, where a default cookie store authenticates a bearer-less request as the previous user."
        )
        client.keychain.removeAll()
    }

    func testI3ConcurrentRequestsDuringRefreshShareOneRefresh() async throws {
        let alice = try await Fixture.user("i3")
        let client = Fixture.client("i3")
        _ = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        try await Fixture.moveServerRefreshTimer()
        let before = try XCTUnwrap(client.auth.currentSession)
        while !(client.auth.currentSession?.isExpired ?? false) {
            try await Task.sleep(for: .seconds(1))
        }
        let responses = try await withThrowingTaskGroup(of: (Int, String).self) { group in
            for _ in 0..<8 {
                group.addTask {
                    let token = try await client.auth.session.accessToken
                    let response = try await client.request("GET", "/me")
                    return (response.status, token)
                }
            }
            return try await group.reduce(into: [(Int, String)]()) { $0.append($1) }
        }
        let tokens = Set(responses.map(\.1))
        let rotated = client.auth.currentSession?.refreshToken != before.refreshToken
        let oldRefresh = try await Fixture.rawRefresh(before.refreshToken)
        probeResult(
            "I3", area: "refresh-race",
            scenario: "Eight concurrent requests start after the access token entered its refresh margin",
            expected: "One refresh (one new access token shared by all), every request 200, rotated token persisted",
            observed: [
                "statuses": responses.map(\.0).sorted(),
                "distinct_access_tokens": tokens.count,
                "refresh_token_rotated": rotated,
                "previous_refresh_token_status_after_window": oldRefresh,
            ],
            ok: responses.allSatisfy { $0.0 == 200 } && tokens.count == 1 && rotated,
            note: "supabase-swift's SessionManager actor shares one in-flight refresh task."
        )
        client.keychain.removeAll()
    }

    func testI4SessionRevokedElsewhereSignsThisDeviceOut() async throws {
        let alice = try await Fixture.user("i4")
        let phone = Fixture.client("i4-phone")
        let tablet = Fixture.client("i4-tablet")
        _ = try await phone.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        _ = try await tablet.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        try await tablet.auth.signOut(scope: .global)
        var outcome = "none"
        do {
            _ = try await phone.request("GET", "/me")
        } catch ArgusAuthError.signedOut {
            outcome = "signedOut"
        }
        probeResult(
            "I4", area: "revoke",
            scenario: "Another device signs out everywhere; this device makes its next request",
            expected: "401, one refresh attempt refused, local session cleared, app shows signed out",
            observed: ["outcome": outcome, "local_session_cleared": phone.auth.currentSession == nil],
            ok: outcome == "signedOut" && phone.auth.currentSession == nil
        )
    }

    func testI5LogoutRevokesButForgettingDoesNot() async throws {
        let alice = try await Fixture.user("i5")
        let forgetful = Fixture.client("i5-forget")
        _ = try await forgetful.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let forgotten = try XCTUnwrap(forgetful.auth.currentSession)
        await forgetful.forgetLocally()
        let forgottenRefresh = try await Fixture.rawRefresh(forgotten.refreshToken)

        let proper = Fixture.client("i5-signout")
        _ = try await proper.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let revoked = try XCTUnwrap(proper.auth.currentSession)
        try await proper.signOut()
        let oldAccess = try await proper.transport.send("GET", "/me", bearer: revoked.accessToken)
        let revokedRefresh = try await Fixture.rawRefresh(revoked.refreshToken)
        probeResult(
            "I5", area: "logout",
            scenario: "Clearing local state versus signOut(scope: .local)",
            expected: "Forgotten refresh token still works server-side; after sign-out both tokens are dead",
            observed: [
                "forgotten_refresh_status": forgottenRefresh,
                "signout_local_session_cleared": proper.auth.currentSession == nil,
                "signout_old_access_status": oldAccess.status,
                "signout_old_refresh_status": revokedRefresh,
            ],
            ok: forgottenRefresh == 200 && oldAccess.status == 401 && revokedRefresh != 200,
            note: "supabase-swift removes the local session before the network revoke and does not retry it. An offline sign-out leaves the server session live (see report)."
        )
    }

    func testI6AccountSwitchDropsInFlightResponse() async throws {
        let alice = try await Fixture.user("i6a")
        let bob = try await Fixture.user("i6b")
        let client = Fixture.client("i6")
        _ = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        _ = try await client.request("GET", "/me", cacheKey: "me")
        let started = AsyncStream<Void>.makeStream()
        let pending = Task {
            try await client.request("GET", "/me", cacheKey: "me", onStarted: { started.continuation.yield() })
        }
        for await _ in started.stream { break }
        try await client.signOut()
        _ = try await client.signIn(email: bob.email, password: bob.password, captchaToken: Env.captcha)
        var aliceDelivered = false
        var stale = false
        do {
            let late = try await pending.value
            aliceDelivered = ((late.body["user"] as? [String: Any])?["email"] as? String) == alice.email
        } catch ArgusAuthError.staleAccount {
            stale = true
        }
        let cachedAfterSwitch = await client.boundary.cached("me")
        let bobMe = try await client.request("GET", "/me")
        let bobEmail = (bobMe.body["user"] as? [String: Any])?["email"] as? String
        probeResult(
            "I6", area: "account-switch",
            scenario: "Alice's request is in flight when the user switches to Bob",
            expected: "Alice's late response is dropped; Alice's cache is gone; Bob sees Bob",
            observed: [
                "late_response_dropped": stale,
                "alice_data_delivered_after_switch": aliceDelivered,
                "alice_cache_survived": cachedAfterSwitch != nil,
                "bob_is_bob": bobEmail == bob.email,
            ],
            ok: stale && !aliceDelivered && cachedAfterSwitch == nil && bobEmail == bob.email,
            note: "The server cannot do this for the client. The web has the same rule in chat-request-session.ts and a known resend gap (#688)."
        )
        try await client.signOut()
    }

    func testI11SecretsStayOutOfLogs() async throws {
        let alice = try await Fixture.user("i11")
        let logger = CapturingLogger()
        let client = ArgusNativeClient(
            stack: Env.stack, keychainService: "argus.native.proof.\(Env.runID).i11",
            callback: Env.callback, deviceIP: Fixture.deviceIP(), logger: logger
        )
        _ = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let before = try XCTUnwrap(client.auth.currentSession)
        _ = try await client.auth.refreshSession()
        let after = try XCTUnwrap(client.auth.currentSession)
        let logged = logger.lines.joined(separator: "\n")
        let secrets = [before.refreshToken, before.accessToken, after.refreshToken, after.accessToken]
        let describedSession = String(describing: after)
        probeResult(
            "I11", area: "secrets",
            scenario: "An app passes a logger to supabase-swift, or logs a Session value",
            expected: "No access or refresh token appears in log output",
            observed: [
                "sdk_log_lines": logger.lines.count,
                "sdk_logger_output_contains_token": secrets.contains { logged.contains($0) },
                "session_description_contains_token": secrets.contains { describedSession.contains($0) },
            ],
            ok: !secrets.contains { logged.contains($0) } && !secrets.contains { describedSession.contains($0) },
            note: "Failed assumption when true. The SDK attaches the refresh token to its logger context during refresh, and Session has no redacting description. Ship with logger: nil and never interpolate Session."
        )
        try await client.signOut()
    }
}

final class CapturingLogger: SupabaseLogger, @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String] = []

    var lines: [String] {
        lock.lock()
        defer { lock.unlock() }
        return storage
    }

    func log(message: SupabaseLogMessage) {
        lock.lock()
        storage.append(message.description)
        lock.unlock()
    }
}

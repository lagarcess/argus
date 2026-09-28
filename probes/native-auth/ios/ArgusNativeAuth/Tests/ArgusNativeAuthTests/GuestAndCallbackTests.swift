import ArgusNativeAuth
import Auth
import Foundation
import XCTest

final class GuestAndCallbackTests: XCTestCase {
    private func guestConversation(_ client: ArgusNativeClient) async throws -> String {
        _ = try await client.startGuest(captchaToken: Env.captcha)
        let created = try await client.request("POST", "/conversations", json: ["title": NSNull()])
        return try XCTUnwrap((created.body["conversation"] as? [String: Any])?["id"] as? String)
    }

    private func conversations(_ client: ArgusNativeClient) async throws -> Set<String> {
        let list = try await client.request("GET", "/conversations")
        return Set((list.body["items"] as? [[String: Any]] ?? []).compactMap { $0["id"] as? String })
    }

    func testI7GuestConversionWithScopedHandoffCookies() async throws {
        let alice = try await Fixture.user("i7")
        let client = Fixture.client("i7", transport: .scopedCookies)
        let conversation = try await guestConversation(client)
        try await client.createHandoff(destinationEmail: alice.email, conversationID: conversation)
        let heldHandoff = client.handoffs.current != nil
        let outcome = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)
        let owned = try await conversations(client)
        probeResult(
            "I7", area: "scoped-jar-conversion",
            scenario: "Guest converts to an existing account; the app keeps only the two handoff cookies in Keychain",
            expected: "Sign-in claims the guest conversation; handoff deleted; no other cookie kept",
            observed: [
                "handoff_held_before_sign_in": heldHandoff,
                "claimed_conversation_matches": outcome.claimedConversationID == conversation,
                "conversation_owned_by_account": owned.contains(conversation),
                "handoff_after_sign_in": client.handoffs.current != nil,
                "shared_cookie_store_empty": (HTTPCookieStorage.shared.cookies ?? []).isEmpty,
            ],
            ok: outcome.claimedConversationID == conversation && owned.contains(conversation)
                && client.handoffs.current == nil
        )
        try await client.signOut()
    }

    func testI8GuestConversionWithHeaderTransport() async throws {
        let alice = try await Fixture.user("i8")
        let bob = try await Fixture.user("i8b")
        let client = Fixture.client("i8", transport: .header, argusBase: Env.adapter)
        let conversation = try await guestConversation(client)
        try await client.createHandoff(destinationEmail: alice.email, conversationID: conversation)
        let heldHandoff = client.handoffs.current != nil
        let outcome = try await client.signIn(email: alice.email, password: alice.password, captchaToken: Env.captcha)

        let wrong = Fixture.client("i8-wrong", transport: .header, argusBase: Env.adapter)
        let other = try await guestConversation(wrong)
        try await wrong.createHandoff(destinationEmail: alice.email, conversationID: other)
        var wrongCode: String?
        do {
            _ = try await wrong.signIn(email: bob.email, password: bob.password, captchaToken: Env.captcha)
        } catch let ArgusAuthError.rejected(_, code) {
            wrongCode = code
        }
        probeResult(
            "I8", area: "bearer-only-conversion",
            scenario: "Same conversion over the proposed header transport, plus a wrong-account sign-in",
            path: "synthetic-header-adapter", level: 2,
            expected: "Claim succeeds with no cookies at all; wrong account gets wrong_destination and its session is revoked, not orphaned",
            observed: [
                "handoff_held_before_sign_in": heldHandoff,
                "claimed_conversation_matches": outcome.claimedConversationID == conversation,
                "handoff_after_sign_in": client.handoffs.current != nil,
                "wrong_account_code": wrongCode ?? "none",
                "wrong_account_local_session": wrong.auth.currentSession != nil,
            ],
            ok: outcome.claimedConversationID == conversation && client.handoffs.current == nil
                && wrongCode == "guest_handoff_wrong_destination" && wrong.auth.currentSession == nil,
            note: "Runs on the simulator, but through the synthetic adapter, so it is level 2 for the Argus contract."
        )
        try await client.signOut()
    }

    func testI9NewAccountConversionSurvivesRelaunch() async throws {
        let email = Fixture.email("i9")
        try await Fixture.allowlist(email)
        let password = Fixture.password()
        let ip = Fixture.deviceIP()
        let client = Fixture.client("i9", deviceIP: ip)
        let conversation = try await guestConversation(client)
        try await client.createHandoff(destinationEmail: email, conversationID: conversation, kind: "new_account_signup")
        let sentAt = Date()
        let signup = try await client.signUpFromGuest(email: email, password: password, captchaToken: Env.captcha)
        let link = try await Fixture.latestAuthLink(to: email, after: sentAt)
        _ = try await Fixture.callbackURL(for: link)
        let relaunched = Fixture.client("i9", deviceIP: ip)
        let heldAfterRelaunch = relaunched.handoffs.current != nil
        let outcome = try await relaunched.signIn(email: email, password: password, captchaToken: Env.captcha)
        probeResult(
            "I9", area: "new-account-conversion",
            scenario: "Guest signs up, confirms by email outside the app, relaunches, signs in",
            expected: "Signup returns no session; the handoff survives relaunch in Keychain and claims on sign-in",
            observed: [
                "signup_session_present": signup.body["session"] is [String: Any],
                "handoff_after_relaunch": heldAfterRelaunch,
                "claimed_conversation_matches": outcome.claimedConversationID == conversation,
            ],
            ok: !(signup.body["session"] is [String: Any]) && heldAfterRelaunch
                && outcome.claimedConversationID == conversation
        )
        try await relaunched.signOut()
    }

    func testI10RecoveryCallbackHandling() async throws {
        let alice = try await Fixture.user("i10")
        let phone = Fixture.client("i10")
        let sentAt = Date()
        try await phone.requestRecovery(email: alice.email)
        let callback = try await Fixture.callbackURL(for: try await Fixture.latestAuthLink(to: alice.email, after: sentAt))
        let session = try await phone.completeCallback(callback)
        let me = try await phone.request("GET", "/me")

        func failure(_ client: ArgusNativeClient, _ url: URL) async -> String {
            do {
                _ = try await client.completeCallback(url)
                return "accepted"
            } catch let AuthError.api(_, code, _, _) {
                return code.rawValue
            } catch {
                return String(describing: type(of: error))
            }
        }
        let repeated = await failure(phone, callback)
        try await Task.sleep(for: .seconds(2))
        let laptop = Fixture.client("i10-other-device")
        let sentAgain = Date()
        try await phone.requestRecovery(email: alice.email)
        let fresh = try await Fixture.callbackURL(for: try await Fixture.latestAuthLink(to: alice.email, after: sentAgain))
        let foreign = await failure(laptop, fresh)
        let forged = await failure(phone, URL(string: "argusnativeproof://auth-callback?code=00000000-0000-0000-0000-000000000000")!)
        let errorURL = URL(string: "argusnativeproof://auth-callback?error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired")!
        let expired = await failure(phone, errorURL)
        probeResult(
            "I10", area: "recovery",
            scenario: "App callback handling for valid, repeated, foreign-device, forged, and expired recovery callbacks",
            expected: "Only the first valid callback on the requesting device yields a session",
            observed: [
                "valid_callback_session": !session.accessToken.isEmpty,
                "argus_me_status": me.status,
                "repeated": repeated,
                "other_device": foreign,
                "forged": forged,
                "expired_link_error_callback": expired,
            ],
            ok: me.status == 200 && repeated != "accepted" && foreign != "accepted"
                && forged != "accepted" && expired != "accepted",
            note: "Callback URLs are handed to the SDK in-process. Delivery of a custom-scheme URL to the app is shown separately with simctl openurl; universal links are not verified."
        )
        try await phone.signOut()
    }
}

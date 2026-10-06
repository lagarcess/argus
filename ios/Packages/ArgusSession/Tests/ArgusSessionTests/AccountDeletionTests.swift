import Auth
import Foundation
import XCTest
@testable import ArgusSession

private actor DeletionServer {
    let auth = AuthServer()
    var status = 200
    var body: [String: Any] = ["status": "done", "pending": []]
    var retry: String?
    var loseResponse = false
    var requests: [URLRequest] = []
    var gate: RequestGate?
    var sdkUserGate: RequestGate?
    func configure(_ status: Int, _ body: [String: Any], retry: String? = nil, lose: Bool = false) {
        self.status = status; self.body = body; self.retry = retry; loseResponse = lose
    }
    func hold(_ gate: RequestGate) { self.gate = gate }
    func holdSDKUser(_ gate: RequestGate) { sdkUserGate = gate }
    func captured() -> [URLRequest] { requests }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        guard request.url!.path.hasSuffix("/account/delete") else {
            if request.url!.path.hasSuffix("/user"), let sdkUserGate { await sdkUserGate.enter() }
            return try await auth.send(request)
        }
        requests.append(request)
        if let gate { await gate.enter() }
        if loseResponse { throw URLError(.networkConnectionLost) }
        var headers = ["Content-Type": "application/json"]
        if let retry { headers["Retry-After"] = retry }
        return (try JSONSerialization.data(withJSONObject: body),
            HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: headers)!)
    }
}

private struct DeletionFixture {
    let server = DeletionServer()
    let storage = MemoryStore()
    let configuration = try! SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!,
        supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
    func controller() throws -> SessionController {
        try SessionController(configuration: configuration, storage: storage, fetch: { [server] in try await server.send($0) })
    }
    func login(_ controller: SessionController) async throws -> SessionSnapshot {
        try await controller.login(email: "alice@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
    }
    func journal() throws -> AccountDeletionJournal? {
        try CredentialVault(backing: storage, prefix: configuration.storagePrefix).deletionJournal()
    }
}

final class AccountDeletionTests: XCTestCase {
    func testDoneIssuesOwnerReceiptAndRetiresWithoutRefreshOrCapture() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        let beforeRefresh = await fixture.server.auth.count("/token")
        let result = try await controller.deleteAccount(expectedIdentity: identity, freshAppleAuthorizationCode: "fresh-code")
        guard case .completed(let receipt) = result else { return XCTFail("Expected server completion") }
        XCTAssertEqual(receipt.userID.uuidString.lowercased(), identity.profile!.id.lowercased())
        XCTAssertEqual(receipt.initiatingRevision, identity.revision)
        let snapshot = await controller.snapshot(); XCTAssertEqual(snapshot.phase, .signedOut)
        XCTAssertNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".session"))
        let requests = await fixture.server.captured(); XCTAssertEqual(requests.count, 1)
        let body = try JSONSerialization.jsonObject(with: requests[0].httpBody!) as! [String: Any]
        XCTAssertEqual(body["confirm"] as? Bool, true)
        XCTAssertEqual(body["apple_authorization_code"] as? String, "fresh-code")
        XCTAssertNil(body["user_id"])
        let afterRefresh = await fixture.server.auth.count("/token"); XCTAssertEqual(afterRefresh, beforeRefresh)
        let captures = await fixture.server.auth.count("/authorization-code"); XCTAssertEqual(captures, 0)
        let journalData = try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".deletion")!
        XCTAssertFalse(String(decoding: journalData, as: UTF8.self).contains("fresh-code"))
    }

    func testAcceptedRetiresProofAndRelaunchCannotRetry() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        await fixture.server.configure(202, ["status": "in_progress", "pending": ["apple"]])
        let result = try await controller.deleteAccount(expectedIdentity: identity)
        XCTAssertEqual(result, .pending(userID: UUID(uuidString: identity.profile!.id)!))
        let restored = try fixture.controller(); let snapshot = try await restored.restore()
        XCTAssertEqual(snapshot.phase, .accountDeletionPending)
        XCTAssertNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".session"))
        do { _ = try await restored.resumePendingAccountDeletion(); XCTFail("Accepted deletion has no interactive proof") }
        catch { XCTAssertEqual(error as? SessionFailure, .staleOperation) }
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
    }

    func testLostResponseSurvivesRelaunchAndBlocksProtectedDispatchBeforeSameCommandResolution() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        await fixture.server.configure(200, ["status": "done", "pending": []], lose: true)
        let result = try await controller.deleteAccount(expectedIdentity: identity, freshAppleAuthorizationCode: "one-use-code")
        guard case .uncertain = result else { return XCTFail("Lost response is uncertain") }
        XCTAssertEqual(try fixture.journal()?.phase, .uncertain)
        XCTAssertNotNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".session"))
        do { _ = try await controller.financialAccounts(expectedIdentity: identity); XCTFail("Quarantined") } catch {}
        do { _ = try await controller.signOut(); XCTFail("Cannot discard recovery proof") }
        catch { XCTAssertEqual(error as? SessionFailure, .accountDeletionInProgress) }
        let restored = try fixture.controller(); let snapshot = try await restored.restore()
        XCTAssertEqual(snapshot.phase, .accountDeletionUncertain)
        await fixture.server.configure(200, ["status": "done", "pending": []])
        _ = try await restored.resumePendingAccountDeletion()
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 2)
        let body = try JSONSerialization.jsonObject(with: commands[1].httpBody!) as! [String: Any]
        XCTAssertNil(body["apple_authorization_code"], "Never replay one-time code")
        XCTAssertEqual(commands[0].value(forHTTPHeaderField: "Authorization"), commands[1].value(forHTTPHeaderField: "Authorization"))
    }

    func testUnauthorizedNeverRefreshesAndKeepsUncertaintyForSupport() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        let before = await fixture.server.auth.count("/token")
        await fixture.server.configure(401, ["code": "unauthorized"])
        let result = try await controller.deleteAccount(expectedIdentity: identity)
        guard case .uncertain(_, _, let canRetry, _) = result else { return XCTFail("Unauthorized does not prove intact account") }
        XCTAssertFalse(canRetry)
        _ = try await controller.resumePendingAccountDeletion()
        let after = await fixture.server.auth.count("/token"); XCTAssertEqual(after, before)
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
    }

    func testNoAdmissionRefusalsRestoreCurrentIdentityAndNeverClearCredentials() async throws {
        let cases: [(Int, String, AccountDeletionRefusal)] = [
            (409, "apple_reauthorization_required", .freshAppleAuthorizationRequired),
            (409, "apple_identity_mismatch", .freshAppleAuthorizationRequired),
            (400, "apple_authorization_invalid", .freshAppleAuthorizationRequired),
            (503, "account_deletion_unavailable", .unavailable),
            (403, "account_deletion_not_allowed", .forbidden), (404, "not_found", .disabled)]
        for (status, code, expected) in cases {
            let fixture = DeletionFixture(); let controller = try fixture.controller()
            let identity = try await fixture.login(controller)
            await fixture.server.configure(status, ["code": code])
            let result = try await controller.deleteAccount(expectedIdentity: identity)
            XCTAssertEqual(result, .refused(expected))
            let snapshot = await controller.snapshot(); XCTAssertEqual(snapshot, identity)
            XCTAssertNil(try fixture.journal())
            XCTAssertNotNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".session"))
        }
    }

    func testIncompleteHonorsRetryAfterAndMalformedDoneCannotIssueReceipt() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        await fixture.server.configure(503, ["code": "account_deletion_incomplete"], retry: "5")
        let result = try await controller.deleteAccount(expectedIdentity: identity)
        guard case .uncertain(_, let retry, _, _) = result else { return XCTFail("Incomplete") }
        XCTAssertNotNil(retry)
        do { _ = try await controller.resumePendingAccountDeletion(); XCTFail("Retry too soon") }
        catch { XCTAssertEqual(error as? SessionFailure, .busy) }
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
        let data = try JSONSerialization.data(withJSONObject: ["status": "done", "pending": ["apple"]])
        let response = HTTPURLResponse(url: URL(string: "https://api.example.test")!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        if case .uncertain = AccountDeletionResponse.parse(data, response: response) {} else { XCTFail("Malformed done cannot complete") }
    }

    func testJournalFailureHasNoCommandEffects() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        fixture.storage.failedWriteSuffix = ".deletion"
        do { _ = try await controller.deleteAccount(expectedIdentity: identity); XCTFail("No durable intent") }
        catch { XCTAssertEqual(error as? SessionFailure, .storageUnavailable) }
        let commands = await fixture.server.captured(); XCTAssertTrue(commands.isEmpty)
    }

    func testInterruptedCompletedCleanupReceiptCanBeRecoveredAndAcknowledged() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        fixture.storage.failRemoves = true
        do { _ = try await controller.deleteAccount(expectedIdentity: identity); XCTFail("Credential removal failed") }
        catch { XCTAssertEqual(error as? SessionFailure, .storageUnavailable) }
        XCTAssertEqual(try fixture.journal()?.phase, .completed)
        fixture.storage.failRemoves = false
        let restored = try fixture.controller(); _ = try await restored.restore()
        let status = try await restored.accountDeletionStatus(userID: UUID(uuidString: identity.profile!.id)!)
        guard case .completed(let receipt) = status else { return XCTFail("Durable cleanup obligation") }
        try await restored.acknowledgeConfirmedAccountDeletion(receipt)
        XCTAssertNil(try fixture.journal())
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
    }

    func testAcceptedAcknowledgementAllowsAnotherAccountWithoutRetiringIt() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let alice = try await fixture.login(controller)
        await fixture.server.configure(202, ["status": "in_progress", "pending": []])
        _ = try await controller.deleteAccount(expectedIdentity: alice)
        let bob = try await controller.login(email: "bob@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
        XCTAssertNotEqual(alice.profile?.id, bob.profile?.id)
        let restored = try fixture.controller(); let snapshot = try await restored.restore()
        XCTAssertEqual(snapshot.profile?.id, bob.profile?.id)
        let acknowledgement = try await restored.accountDeletionStatus(userID: UUID(uuidString: alice.profile!.id)!)
        XCTAssertEqual(acknowledgement, .pending(userID: UUID(uuidString: alice.profile!.id)!))
        do { _ = try await controller.deleteAccount(expectedIdentity: alice); XCTFail("Stale owner") }
        catch { XCTAssertEqual(error as? SessionFailure, .staleOperation) }
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
    }

    func testRecoveryRefusalCannotTurnLostResponseIntoNoAdmission() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        await fixture.server.configure(503, ["code": "account_deletion_incomplete"])
        _ = try await controller.deleteAccount(expectedIdentity: identity)
        await fixture.server.configure(409, ["code": "apple_reauthorization_required"])
        let result = try await controller.resumePendingAccountDeletion()
        guard case .uncertain(_, _, _, let recovery) = result else { return XCTFail("Earlier uncertainty survives") }
        XCTAssertEqual(recovery, .freshAppleAuthorizationRequired)
        XCTAssertEqual(try fixture.journal()?.phase, .uncertain)
        let snapshot = await controller.snapshot(); XCTAssertEqual(snapshot.phase, .accountDeletionUncertain)
    }

    func testConcurrentDuplicateIsDeniedWhileJournalAlreadyQuarantinesProtectedWork() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        let gate = RequestGate(); await fixture.server.hold(gate)
        let command = Task { try await controller.deleteAccount(expectedIdentity: identity) }
        await gate.waitUntilStarted()
        XCTAssertEqual(try fixture.journal()?.phase, .uncertain)
        do { _ = try await controller.deleteAccount(expectedIdentity: identity); XCTFail("Duplicate") } catch {}
        do { _ = try await controller.financialAccounts(expectedIdentity: identity); XCTFail("Protected dispatch") } catch {}
        await gate.release(); _ = try await command.value
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
        let financial = await fixture.server.auth.count("/financial-accounts"); XCTAssertEqual(financial, 0)
    }

    func testExpiredProofUsesSupportWithoutRefreshOrDispatch() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let identity = try await fixture.login(controller)
        await fixture.server.configure(503, ["code": "account_deletion_incomplete"])
        _ = try await controller.deleteAccount(expectedIdentity: identity)
        await fixture.server.auth.configure(expired: true)
        let expired = try await fixture.server.auth.sessionData()
        try fixture.storage.store(key: fixture.configuration.storagePrefix + ".session", value: expired)
        let before = await fixture.server.auth.count("/token")
        let restored = try fixture.controller(); _ = try await restored.restore()
        let result = try await restored.resumePendingAccountDeletion()
        guard case .uncertain(_, _, let canRetry, _) = result else { return XCTFail("Expired proof remains uncertain") }
        XCTAssertFalse(canRetry)
        let after = await fixture.server.auth.count("/token"); XCTAssertEqual(after, before)
        let commands = await fixture.server.captured(); XCTAssertEqual(commands.count, 1)
    }


    func testAcceptedAJournalCannotRetireBDuringSDKAdoption() async throws {
        let fixture = DeletionFixture(); let controller = try fixture.controller()
        let alice = try await fixture.login(controller)
        await fixture.server.configure(202, ["status": "in_progress", "pending": []])
        _ = try await controller.deleteAccount(expectedIdentity: alice)
        let gate = RequestGate(); await fixture.server.holdSDKUser(gate)
        let login = Task { try await controller.login(email: "bob@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha") }
        await gate.waitUntilStarted()
        XCTAssertNotNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".pending"))
        do { _ = try await controller.signOut(); XCTFail("Cannot interrupt B adoption") }
        catch { XCTAssertEqual(error as? SessionFailure, .busy) }
        do { _ = try await controller.retryPendingSignOut(); XCTFail("Cannot retire B issued proof") }
        catch { XCTAssertEqual(error as? SessionFailure, .busy) }
        do { _ = try await controller.requestCredentialRevalidation(); XCTFail("Cannot restore A during B adoption") }
        catch { XCTAssertEqual(error as? SessionFailure, .busy) }
        XCTAssertNotNil(try fixture.storage.retrieve(key: fixture.configuration.storagePrefix + ".pending"))
        await gate.release(); let bob = try await login.value
        XCTAssertNotEqual(bob.profile?.id, alice.profile?.id)
        let snapshot = await controller.snapshot(); XCTAssertEqual(snapshot, bob)
    }

}

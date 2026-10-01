import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class HouseholdModelTests: XCTestCase {
    func testDefaultOffAndUnavailableDiscoveryNeverClaimMembershipLoss() async throws {
        for status in [404, 503] {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login(discover: false)
            XCTAssertEqual(fixture.model.availability, .discovering)
            XCTAssertFalse(fixture.model.active)
            await fixture.server.failNext(status, code: status == 404 ? "households_unavailable" : "unavailable")
            await fixture.model.refresh()
            XCTAssertEqual(fixture.model.availability, status == 404 ? .disabled : .unavailable)
            XCTAssertFalse(fixture.model.isAvailable)
            XCTAssertNil(fixture.model.selectedId)
            XCTAssertTrue(fixture.model.households.isEmpty)
            XCTAssertNotEqual(fixture.model.errorKey, "household.accessEnded")
            await fixture.model.command(HouseholdCommand(name: "Must not dispatch", displayName: "Alice"), path: "")
            let creates = await fixture.server.creates
            XCTAssertTrue(creates.isEmpty)
            await fixture.model.foreground()
            XCTAssertTrue(fixture.model.isAvailable)
        }
    }
    func testSelectedHouseholdOffAcrossEntryPointsClearsProtectedStateAndRestoresSelection() async throws {
        for entry in ["refresh", "detail", "history", "search", "invitation", "editorLoad", "editorReview", "command"] {
            let fixture = try HouseholdFixture()
            let identity = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            await fixture.model.open(HouseholdServer.account)
            await fixture.model.versionCommand("/invitations")
            await fixture.model.previewInvitation("synthetic-test-capability")
            XCTAssertNotNil(fixture.model.invitationPreview)
            fixture.model.showManagement = true
            fixture.model.beginActivity(try XCTUnwrap(fixture.model.snapshot?.accounts.first))
            let editor = try XCTUnwrap(fixture.model.editor)
            editor.amount = "25"
            await fixture.server.setEnabled(false)
            switch entry {
            case "refresh": await fixture.model.refresh()
            case "detail": await fixture.model.open(HouseholdServer.account)
            case "history": await fixture.model.loadHistory(UUID())
            case "search": await fixture.model.find("private query")
            case "invitation": await fixture.model.previewInvitation("synthetic-test-capability")
            case "editorLoad": await editor.load()
            case "editorReview": await editor.review(Locale(identifier: "en_US"))
            default: await fixture.model.versionCommand("/invitations")
            }
            XCTAssertEqual(fixture.model.availability, .disabled, entry)
            XCTAssertFalse(fixture.model.active, entry)
            XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household, entry)
            XCTAssertNil(fixture.model.household, entry)
            XCTAssertNil(fixture.model.snapshot, entry)
            XCTAssertNil(fixture.model.detail, entry)
            XCTAssertTrue(fixture.model.history.isEmpty, entry)
            XCTAssertTrue(fixture.model.search.isEmpty, entry)
            XCTAssertTrue(fixture.model.households.isEmpty, entry)
            XCTAssertNil(fixture.model.invitation, entry)
            XCTAssertNil(fixture.model.invitationPreview, entry)
            XCTAssertNil(fixture.model.editor, entry)
            XCTAssertFalse(fixture.model.showManagement, entry)
            XCTAssertFalse(fixture.model.busy, entry)
            XCTAssertNil(fixture.model.errorKey, entry)
            let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
            reopened.bind(identity)
            XCTAssertEqual(reopened.selectedId, HouseholdServer.household, entry)
            await fixture.server.setEnabled(true)
            await reopened.foreground()
            XCTAssertTrue(reopened.active, entry)
            XCTAssertEqual(reopened.household?.id, HouseholdServer.household, entry)
            XCTAssertNotNil(reopened.snapshot, entry)
        }
    }
    func testScopedAccessLossClearsSelectionButOther404And403DoNot() async throws {
        for (status, code, ended) in [(404, "household_not_found", true), (403, "not_a_member", true), (404, "invitation_not_found", false), (403, "household_admin_required", false)] {
            let fixture = try HouseholdFixture()
            let identity = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            await fixture.server.failNext(status, code: code)
            if ended { await fixture.model.open(HouseholdServer.account) }
            else { await fixture.model.previewInvitation("invalid-invitation") }
            XCTAssertTrue(fixture.model.isAvailable, code)
            XCTAssertEqual(fixture.model.selectedId, ended ? nil : HouseholdServer.household, code)
            XCTAssertEqual(fixture.model.errorKey == "household.accessEnded", ended, code)
            let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
            reopened.bind(identity)
            XCTAssertEqual(reopened.selectedId, ended ? nil : HouseholdServer.household, code)
        }
    }
    func testCommittedPendingRetryWhileOffPreservesExactJournalThroughRelaunch() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        await fixture.server.failCreateOnce()
        await fixture.model.command(HouseholdCommand(name: "Committed once", displayName: "Alice"), path: "")
        let pending = try XCTUnwrap(fixture.model.pending)
        await fixture.server.setEnabled(false)
        await fixture.model.retry()
        XCTAssertEqual(fixture.model.availability, .disabled)
        XCTAssertEqual(fixture.model.pending, pending)
        XCTAssertEqual(try fixture.journal.pending(for: identity), pending)
        XCTAssertFalse(fixture.model.busy)
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        await reopened.refresh()
        XCTAssertEqual(reopened.pending, pending)
        await fixture.server.setEnabled(true)
        await reopened.foreground()
        let beforeExplicitRetry = await fixture.server.creates
        XCTAssertEqual(beforeExplicitRetry.count, 1, "Restoring the surface must never retry a write automatically")
        XCTAssertEqual(reopened.pending, pending)
        await reopened.retry()
        let requests = await fixture.server.creates
        XCTAssertEqual(requests.count, 2)
        XCTAssertEqual(requests[0].httpBody, requests[1].httpBody)
        XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Idempotency-Key"), requests[1].value(forHTTPHeaderField: "Idempotency-Key"))
        XCTAssertEqual(reopened.selectedId, HouseholdServer.household)
        XCTAssertNil(reopened.pending)
        XCTAssertNil(try fixture.journal.pending(for: identity))
    }
    func testDelayedDiscoveryCannotRestoreDisabledOrSignedOutOrChangedIdentity() async throws {
        for transition in ["off", "signOut", "newActor"] {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            let gate = RequestGate(); await fixture.server.holdDiscovery(gate)
            let request = Task { await fixture.model.refresh() }
            await gate.waitUntilStarted()
            if transition == "off" {
                await fixture.server.setEnabled(false); await fixture.model.refresh()
            } else if transition == "signOut" { fixture.model.bind(nil) }
            else {
                fixture.model.bind(try await fixture.controller.signOut())
                let bob = try await fixture.controller.login(email: "bob@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
                fixture.model.bind(bob)
            }
            await gate.release(); await request.value
            XCTAssertFalse(fixture.model.active, transition)
            XCTAssertTrue(fixture.model.households.isEmpty, transition)
            XCTAssertNil(fixture.model.snapshot, transition)
            XCTAssertNil(fixture.model.household, transition)
            XCTAssertEqual(fixture.model.availability, transition == "off" ? .disabled : .discovering, transition)
            if transition != "off" { XCTAssertNil(fixture.model.selectedId, transition) }
        }
    }
    func testScopeChangesReleaseWriteBusyAndPreserveExactRetry() async throws {
        for selectPersonal in [false, true] {
            let fixture = try HouseholdFixture()
            let identity = try await fixture.login(); fixture.model.bind(identity)
            let gate = RequestGate(); await fixture.server.holdCreate(gate)
            let request = Task { await fixture.model.command(HouseholdCommand(name: "Synthetic household", displayName: "Alice"), path: "") }
            await gate.waitUntilStarted()
            let pending = try XCTUnwrap(fixture.model.pending)
            if selectPersonal { await fixture.model.select(nil) }
            else { await fixture.model.foreground() }
            await gate.release(); await request.value
            XCTAssertFalse(fixture.model.busy)
            XCTAssertEqual(fixture.model.pending, pending)
            await fixture.model.retry()
            XCTAssertNil(fixture.model.pending)
            let requests = await fixture.server.creates
            XCTAssertEqual(requests.count, 2)
            XCTAssertEqual(requests[0].httpBody, requests[1].httpBody)
            XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Idempotency-Key"), requests[1].value(forHTTPHeaderField: "Idempotency-Key"))
        }
    }
    func testPreparedInvitationCannotFollowSelectionOrRetryIntoAnotherHousehold() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login(); fixture.model.bind(identity)
        await fixture.model.select(HouseholdServer.household)
        await fixture.model.versionCommand("/invitations")
        XCTAssertNotNil(fixture.model.invitation)
        await fixture.model.select(HouseholdServer.secondHousehold)
        XCTAssertNil(fixture.model.invitation)
        await fixture.model.select(HouseholdServer.household)
        XCTAssertNil(fixture.model.invitation)
        let gate = RequestGate(); await fixture.server.holdInvitation(gate)
        let request = Task { await fixture.model.versionCommand("/invitations") }
        await gate.waitUntilStarted()
        await fixture.model.select(HouseholdServer.secondHousehold)
        await gate.release(); await request.value
        XCTAssertNil(fixture.model.invitation)
        XCTAssertNotNil(fixture.model.pending)
        await fixture.model.retry()
        XCTAssertNil(fixture.model.pending)
        XCTAssertNil(fixture.model.invitation)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.secondHousehold)
    }
    func testChangedAssetDecodesWithRedactedAuthorAndKeepsPersonalAuthorRequired() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login(); fixture.model.bind(identity)
        await fixture.server.useChangedAsset()
        await fixture.model.select(HouseholdServer.household)
        let value = try XCTUnwrap(fixture.model.snapshot?.accounts.first?.account)
        XCTAssertEqual(value.asset?.changes.count, 1)
        XCTAssertNil(value.asset?.changes.first?.recordedBy)
        XCTAssertEqual(value.asset?.personalPositionMinor, 480000)
        await fixture.model.open(HouseholdServer.account)
        XCTAssertEqual(fixture.model.detail?.account.account, value)
        let options = try await fixture.controller.householdResponse(HouseholdActivityOptions.self, path: fixture.model.path(HouseholdServer.household, "/activity-options"), expectedIdentity: identity)
        XCTAssertEqual(options.accounts.first, value)
        let data = try JSONEncoder().encode(value)
        XCTAssertThrowsError(try JSONDecoder().decode(FinancialAccount.self, from: data))
        var body = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        var asset = try XCTUnwrap(body["asset"] as? [String: Any])
        var changes = try XCTUnwrap(asset["changes"] as? [[String: Any]])
        let owner = UUID(); changes[0]["recorded_by"] = owner.uuidString
        asset["changes"] = changes; body["asset"] = asset
        let personal = try JSONDecoder().decode(FinancialAccount.self, from: JSONSerialization.data(withJSONObject: body))
        XCTAssertEqual(personal.asset?.changes.first?.recordedBy, owner)
    }
    func testDelayedDetailCannotReturnAfterAccessGenerationChanges() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        fixture.model.bind(identity)
        await fixture.model.select(HouseholdServer.household)
        let gate = RequestGate()
        await fixture.server.holdDetail(gate)
        let request = Task { await fixture.model.open(HouseholdServer.account) }
        await gate.waitUntilStarted()
        await fixture.server.revokeAccount()
        await fixture.model.refresh()
        XCTAssertEqual(fixture.model.snapshot?.authorizationVersion, 2)
        XCTAssertTrue(fixture.model.snapshot?.accounts.isEmpty == true)
        await gate.release(); await request.value
        XCTAssertNil(fixture.model.detail)
    }
    func testDepartureReturnsToPersonalAndRemovesPersistedSelection() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login(); fixture.model.bind(identity)
        await fixture.model.select(HouseholdServer.household)
        await fixture.server.depart()
        await fixture.model.refresh()
        XCTAssertNil(fixture.model.selectedId)
        XCTAssertFalse(fixture.model.active)
        XCTAssertNil(fixture.model.snapshot)
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        XCTAssertNil(reopened.selectedId)
    }
    func testUncertainCommandSurvivesRelaunchWithExactBodyAndKey() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login(); fixture.model.bind(identity)
        await fixture.server.failCreateOnce()
        await fixture.model.command(HouseholdCommand(name: "Synthetic household", displayName: "Alice"), path: "")
        let pending = try XCTUnwrap(fixture.model.pending)
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        XCTAssertEqual(reopened.pending, pending)
        await reopened.refresh()
        await reopened.retry()
        let requests = await fixture.server.creates
        XCTAssertEqual(requests.count, 2)
        XCTAssertEqual(requests[0].httpBody, requests[1].httpBody)
        XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Idempotency-Key"), requests[1].value(forHTTPHeaderField: "Idempotency-Key"))
        XCTAssertNil(reopened.pending)
    }
    func testDelayedCreateCannotSelectHouseholdAfterSignOut() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login(); fixture.model.bind(identity)
        let gate = RequestGate(); await fixture.server.holdCreate(gate)
        let request = Task { await fixture.model.command(HouseholdCommand(name: "Synthetic household", displayName: "Alice"), path: "") }
        await gate.waitUntilStarted(); fixture.model.bind(nil)
        await gate.release(); await request.value
        XCTAssertNil(fixture.model.selectedId)
        XCTAssertNil(fixture.model.household)
        XCTAssertNil(fixture.model.pending)
    }
}

@MainActor
private struct HouseholdFixture {
    let server = HouseholdServer()
    let configuration: SessionConfiguration
    let controller: SessionController
    let journal: FinancialWriteJournal
    let model: HouseholdModel
    init() throws {
        configuration = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!, supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let storage = MemoryStore(); let server = self.server
        controller = try SessionController(configuration: configuration, storage: storage, fetch: { try await server.send($0) })
        journal = FinancialWriteJournal(storage: storage, prefix: configuration.storagePrefix + ".household")
        model = HouseholdModel(controller: controller, configuration: configuration, journal: journal)
    }
    func login(discover: Bool = true) async throws -> SessionSnapshot {
        let identity = try await controller.login(email: "alice@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
        model.bind(identity)
        if discover { await model.refresh() }
        return identity
    }
}

private actor HouseholdServer {
    let auth = AuthServer()
    static let household = UUID()
    static let secondHousehold = UUID()
    static let member = UUID()
    static let account = UUID()
    private var enabled = true
    private var failure: (status: Int, code: String)?
    private var discoveryGate: RequestGate?
    func setEnabled(_ value: Bool) { enabled = value }
    func failNext(_ status: Int, code: String) { failure = (status, code) }
    func holdDiscovery(_ gate: RequestGate) { discoveryGate = gate }
    private var version = 1
    private var active = true
    private var detailGate: RequestGate?
    private var createGate: RequestGate?
    private var failCreate = false
    private var changedAsset = false
    private var invitationGate: RequestGate?
    private(set) var creates: [URLRequest] = []
    func holdDetail(_ gate: RequestGate) { detailGate = gate }
    func holdCreate(_ gate: RequestGate) { createGate = gate }
    func holdInvitation(_ gate: RequestGate) { invitationGate = gate }
    func useChangedAsset() { changedAsset = true }
    func revokeAccount() { version += 1 }
    func depart() { active = false }
    func failCreateOnce() { failCreate = true }
    func household(_ id: UUID = HouseholdServer.household) -> [String: Any] {
        ["id": id.uuidString, "name": "Synthetic household", "version": version, "membership_id": Self.member.uuidString, "admin_membership_id": Self.member.uuidString, "members": [], "invitations": [], "shares": []]
    }
    func receipt(_ id: UUID) -> [String: Any] {
        ["household_id": id.uuidString, "membership_id": Self.member.uuidString, "state": "active", "replayed": creates.count > 1]
    }
    func account() -> [String: Any] {
        var body: [String: Any] = ["id": Self.account.uuidString, "type": "cash", "nature": "asset", "currency": "DOP", "currency_fraction_digits": 2, "archived": false, "ownership_share_bps": 10000, "version": 1, "created_at": "2026-09-01T12:00:00Z", "updated_at": "2026-09-01T12:00:00Z", "balance": ["state": "unknown", "activity_since_tracking_minor": 0]]
        if changedAsset {
            body["type"] = "property"; body["ownership_share_bps"] = 6000
            body["asset"] = ["personal_position_minor": 480000, "estimates": [], "changes": [["version": 2, "previous_share_bps": 10000, "ownership_share_bps": 6000, "previous_debt_account_id": NSNull(), "related_debt_account_id": NSNull(), "recorded_by": NSNull(), "recorded_at": "2026-09-01T12:00:00Z"]]]
        }
        return ["account": body, "owner_name": "Alice", "permission": "edit", "is_owner": false]
    }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.contains("households") || path.contains("household-invitations") else { return try await auth.send(request) }
        if !enabled { return response(request, 404, ["code": "households_unavailable"]) }
        if let failure {
            self.failure = nil
            return response(request, failure.status, ["code": failure.code])
        }
        var status = 200; var result: [String: Any]
        let householdId = path.contains(Self.secondHousehold.uuidString) ? Self.secondHousehold : Self.household
        if request.httpMethod == "POST" && path.hasSuffix("households") {
            creates.append(request); result = receipt(householdId)
            if failCreate { failCreate = false; status = 503; result = ["code": "unavailable"] }
            if let gate = createGate { createGate = nil; await gate.enter() }
        } else if path.hasSuffix("households") {
            result = ["households": active ? [household(), household(Self.secondHousehold)] : []]
            if let gate = discoveryGate { discoveryGate = nil; await gate.enter() }
        } else if path.hasSuffix("household-invitations/preview") {
            result = ["name": "Synthetic household", "expires_at": "2026-10-08T12:00:00Z", "available": true]
        }
        else if path.hasSuffix("/invitations") {
            result = receipt(householdId)
            result["invitation"] = ["id": UUID().uuidString, "expires_at": "2026-10-08T12:00:00Z", "state": "pending", "token": "synthetic-test-capability"]
            if let gate = invitationGate { invitationGate = nil; await gate.enter() }
        }
        else if path.hasSuffix("/activity-options") { result = ["accounts": [account()["account"]!], "eligibility": [:], "destination_eligibility": [:], "categories": [], "sources": []] }
        else if path.contains("/accounts/") {
            result = ["account": account(), "activities": []]
            if let gate = detailGate { detailGate = nil; await gate.enter() }
        } else if path.hasSuffix("/snapshot") {
            result = ["household_id": householdId.uuidString, "membership_id": Self.member.uuidString, "authorization_version": version, "accounts": version == 1 ? [account()] : [], "activities": [], "positions": []]
        } else { result = household(householdId) }
        return response(request, status, result)
    }
    private func response(_ request: URLRequest, _ status: Int, _ value: [String: Any]) -> (Data, URLResponse) {
        (try! JSONSerialization.data(withJSONObject: value), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
}

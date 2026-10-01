import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class HouseholdModelTests: XCTestCase {
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
    func login() async throws -> SessionSnapshot { try await controller.login(email: "alice@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha") }
}

private actor HouseholdServer {
    let auth = AuthServer()
    static let household = UUID()
    static let secondHousehold = UUID()
    static let member = UUID()
    static let account = UUID()
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
        return ["account": body, "owner_name": "Alice", "permission": "view", "is_owner": false]
    }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.contains("households") else { return try await auth.send(request) }
        var status = 200; var result: [String: Any]
        let householdId = path.contains(Self.secondHousehold.uuidString) ? Self.secondHousehold : Self.household
        if request.httpMethod == "POST" && path.hasSuffix("households") {
            creates.append(request); result = receipt(householdId)
            if failCreate { failCreate = false; status = 503; result = ["code": "unavailable"] }
            if let gate = createGate { createGate = nil; await gate.enter() }
        } else if path.hasSuffix("households") { result = ["households": active ? [household(), household(Self.secondHousehold)] : []] }
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
        return (try JSONSerialization.data(withJSONObject: result), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
}

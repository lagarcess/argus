import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class HouseholdPlanModelTests: XCTestCase {
    func testSnapshotAndSearchDestinationCarryScopeAndReturnContext() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login()
        await f.model.select(SharedPlanTestData.householdId)
        XCTAssertEqual(f.model.plan.state, .ready)
        XCTAssertEqual(f.model.plan.plans.map(\.ref.kind), HouseholdPlanKind.allCases)
        for kind in HouseholdPlanKind.allCases {
            await f.server.searchKind(kind); await f.model.find("Synthetic")
            let hit = try XCTUnwrap(f.model.search.first)
            XCTAssertEqual(hit.kind, .plan); XCTAssertEqual(hit.planRef?.kind, kind)
            await f.model.openSearchHit(hit)
            XCTAssertEqual(f.model.plan.origin, .search)
            XCTAssertEqual(f.model.plan.detail?.ref, hit.planRef)
            XCTAssertEqual(f.model.plan.detail?.ref.kind, kind)
            XCTAssertEqual(f.model.searchQuery, "Synthetic")
            XCTAssertEqual(f.model.searchReturnAnchor, hit.id)
            f.model.plan.back()
            XCTAssertNil(f.model.plan.openedRef)
            XCTAssertEqual(f.model.search.map(\.id), [hit.id])
            XCTAssertEqual(f.model.searchQuery, "Synthetic")
        }
    }
    func testLateDetailAndSnapshotCannotCrossScopeOrSignOut() async throws {
        for entry in ["detail", "snapshot"] {
            let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
            let gate = RequestGate(); await f.server.hold(entry, gate)
            let request = Task { if entry == "detail" { await f.model.plan.open(.init(kind: .goal, id: SharedPlanTestData.planId), origin: .plan) } else { await f.model.plan.refresh() } }
            await gate.waitUntilStarted(); f.model.bind(nil); await gate.release(); await request.value
            XCTAssertNil(f.model.plan.detail, entry); XCTAssertTrue(f.model.plan.plans.isEmpty, entry); XCTAssertNil(f.model.plan.sheet, entry)
        }
    }
    func testDisabledAndRevokedReadClearAllPlanAndPrivateEditorState() async throws {
        for code in ["households_unavailable", "household_access_unavailable"] {
            let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
            let plan = try XCTUnwrap(f.model.plan.plans.first)
            f.model.plan.show(.record(plan, nil)); XCTAssertNotNil(f.model.plan.sheet)
            await f.server.reject(code)
            await f.model.plan.refresh()
            XCTAssertTrue(f.model.plan.plans.isEmpty); XCTAssertNil(f.model.plan.detail); XCTAssertNil(f.model.plan.sheet)
            XCTAssertFalse(f.model.active)
            XCTAssertEqual(f.model.availability, code == "households_unavailable" ? .disabled : .available)
        }
    }
    func testViewerContributionCapabilityNeverGrantsDefinitionOrOtherClaimEditing() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.server.viewer(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first)
        XCTAssertTrue(plan.canContribute); XCTAssertFalse(plan.canEdit)
        f.model.plan.show(.edit(plan)); XCTAssertNil(f.model.plan.sheet)
        f.model.plan.show(.people(plan)); XCTAssertNil(f.model.plan.sheet)
        f.model.plan.show(.record(plan, plan.contributions[0])); XCTAssertNil(f.model.plan.sheet)
        f.model.plan.show(.record(plan, nil)); XCTAssertNotNil(f.model.plan.sheet)
    }
    func testLostResponseRetriesExactTypedBodyOnlyUnderSameScope() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first)
        await f.server.loseNext()
        await f.model.plan.submit(HouseholdPlanEditCommand(scope: f.model.plan.scope(plan), definition: .init(name: "Confirmed title")), action: .edit(plan.ref))
        let pending = try XCTUnwrap(f.model.pending)
        XCTAssertEqual(pending.ownerId.uuidString, f.model.identity?.profile?.id)
        await f.model.select(nil); await f.model.retry()
        let countAfterScopeChange = await f.server.writeCount()
        XCTAssertEqual(countAfterScopeChange, 1)
        XCTAssertEqual(f.model.pending, pending)
        await f.model.select(SharedPlanTestData.householdId); await f.model.retry()
        let writes = await f.server.writes
        XCTAssertEqual(writes.count, 2); XCTAssertEqual(writes[0].httpBody, writes[1].httpBody)
        XCTAssertEqual(writes[0].value(forHTTPHeaderField: "Idempotency-Key"), writes[1].value(forHTTPHeaderField: "Idempotency-Key"))
        XCTAssertNil(f.model.pending)
    }
    func testNewMembershipCannotRetryAnOldConfirmation() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first); await f.server.loseNext()
        await f.model.plan.submit(HouseholdPlanEditCommand(scope: f.model.plan.scope(plan), definition: .init(archived: true)), action: .edit(plan.ref))
        let pending = try XCTUnwrap(f.model.pending)
        await f.server.newMembership(); await f.model.foreground(); await f.model.retry()
        let countAfterMembershipChange = await f.server.writeCount()
        XCTAssertEqual(countAfterMembershipChange, 1); XCTAssertEqual(f.model.pending, pending)
        XCTAssertEqual(f.model.errorKey, "sharedPlan.changed")
    }
    func testDeletedDetailLeavesBackAndSearchOriginAvailable() async throws {
        for code in ["shared_plan_not_found", "household_not_found"] {
            let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId); await f.model.find("Synthetic")
            let hit = try XCTUnwrap(f.model.search.first)
            await f.server.reject(code)
            await f.model.openSearchHit(hit)
            XCTAssertTrue(f.model.plan.detailMissing, code); XCTAssertNil(f.model.plan.detail, code)
            XCTAssertEqual(f.model.plan.errorKey, "sharedPlan.deleted", code); XCTAssertEqual(f.model.searchQuery, "Synthetic", code)
            XCTAssertEqual(f.model.selectedId, SharedPlanTestData.householdId, code)
            XCTAssertEqual(f.model.searchReturnAnchor, hit.id, code)
            f.model.plan.back(); XCTAssertEqual(f.model.search.map(\.id), [hit.id], code)
        }
    }
    func testUniformNotFoundStillEndsAccessWhenHouseholdMembershipIsGone() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId); await f.model.find("Synthetic")
        await f.server.reject("household_not_found", count: 2)
        await f.model.openSearchHit(try XCTUnwrap(f.model.search.first))
        XCTAssertNil(f.model.selectedId); XCTAssertNil(f.model.plan.openedRef); XCTAssertTrue(f.model.search.isEmpty)
        XCTAssertEqual(f.model.errorKey, "household.accessEnded")
    }
    func testContributionConfirmsNormalizedReviewRatherThanEditableDraft() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first)
        f.model.plan.show(.record(plan, nil))
        let editor = HouseholdContributionEditor(model: f.model.plan, plan: plan, correcting: nil)
        await editor.load(); editor.accountId = SharedPlanServer.accountId; editor.amount = "3.75"
        await editor.review(Locale(identifier: "es_419"))
        var reviewed = try XCTUnwrap(editor.preview?.reviewedRequest)
        reviewed.previewToken = try XCTUnwrap(editor.preview?.previewToken)
        await editor.confirm()
        let writes = await f.server.writes
        let request = try XCTUnwrap(writes.first)
        let body = try JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as! [String: Any]
        let confirmed = try JSONDecoder().decode(FinancialActivityCommand.self, from: JSONSerialization.data(withJSONObject: body["activity"]!))
        XCTAssertEqual(confirmed, reviewed)
        XCTAssertEqual(confirmed.note, "Canonical review")
        XCTAssertEqual(confirmed.expectedVersions, [SharedPlanServer.accountId.uuidString: 4])
    }
    func testLateContributionPreviewCannotReappearAfterSignOut() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first); f.model.plan.show(.record(plan, nil))
        let editor = HouseholdContributionEditor(model: f.model.plan, plan: plan, correcting: nil)
        await editor.load(); editor.accountId = SharedPlanServer.accountId; editor.amount = "3.75"
        let gate = RequestGate(); await f.server.hold("preview", gate)
        let request = Task { await editor.review(Locale(identifier: "en_US")) }
        await gate.waitUntilStarted(); f.model.bind(nil); await gate.release(); await request.value
        XCTAssertNil(editor.preview); XCTAssertNil(f.model.plan.sheet)
        let count = await f.server.writeCount(); XCTAssertEqual(count, 0)
    }
}

@MainActor
private struct SharedPlanFixture {
    let server = SharedPlanServer()
    let controller: SessionController
    let model: HouseholdModel
    init() throws {
        let configuration = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!, supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let storage = MemoryStore(), server = self.server
        controller = try SessionController(configuration: configuration, storage: storage, fetch: { try await server.send($0) })
        model = HouseholdModel(controller: controller, configuration: configuration, journal: FinancialWriteJournal(storage: storage, prefix: UUID().uuidString))
    }
    func login() async throws -> SessionSnapshot {
        let identity = try await controller.login(email: "alice@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
        model.bind(identity); await model.refresh(); return identity
    }
}

private actor SharedPlanServer {
    static let accountId = UUID()
    let auth = AuthServer()
    private var gate: (String, RequestGate)?
    private var failure: String?
    private var failuresRemaining = 0
    private var lose = false
    private var isViewer = false
    private var resultKind = HouseholdPlanKind.goal
    private var membership = SharedPlanTestData.memberId
    private(set) var writes: [URLRequest] = []
    func hold(_ entry: String, _ gate: RequestGate) { self.gate = (entry, gate) }
    func reject(_ code: String, count: Int = 1) { failure = code; failuresRemaining = count }
    func loseNext() { lose = true }
    func viewer() { isViewer = true }
    func searchKind(_ kind: HouseholdPlanKind) { resultKind = kind }
    func newMembership() { membership = UUID() }
    func writeCount() -> Int { writes.count }
    func household() -> [String: Any] { ["id": SharedPlanTestData.householdId.uuidString, "name": "Synthetic household", "version": 1, "membership_id": membership.uuidString, "admin_membership_id": membership.uuidString, "members": [], "invitations": [], "shares": []] }
    func plan(_ kind: HouseholdPlanKind) -> [String: Any] {
        var value = SharedPlanTestData.plan(kind); value["membership_id"] = membership.uuidString
        if isViewer { value["permission"] = "view"; value["is_owner"] = false; value["contributions"] = [SharedPlanTestData.contribution()] }
        return value
    }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.hasPrefix("/api/v1/households") else { return try await auth.send(request) }
        if let failure { failuresRemaining -= 1; if failuresRemaining == 0 { self.failure = nil }; return response(request, 404, ["code": failure]) }
        if let gate, (gate.0 == "snapshot" && path.hasSuffix("/plan")) || (gate.0 == "detail" && path.hasSuffix(SharedPlanTestData.planId.uuidString)) || (gate.0 == "preview" && path.hasSuffix("/preview")) { self.gate = nil; await gate.1.enter() }
        if path.hasSuffix("/preview") {
            let reviewed = FinancialActivityCommand(kind: .expense, accountId: Self.accountId, amount: "3.75", occurredAt: "2026-10-01T12:00:00Z", timeZone: "America/Santo_Domingo", note: "Canonical review", expectedVersions: [Self.accountId.uuidString: 4])
            let normalized = try JSONSerialization.jsonObject(with: JSONEncoder().encode(reviewed))
            return response(request, 200, ["plan": plan(.budget), "money": ["ready": true, "expected_versions": [Self.accountId.uuidString: 4], "affected_accounts": [], "reviewed_request": normalized, "preview_token": "review-token"]])
        }
        if request.httpMethod != "GET" {
            writes.append(request)
            if lose { lose = false; return response(request, 503, ["code": "unavailable"]) }
            return response(request, 200, ["plan": plan(.budget), "replayed": writes.count > 1])
        }
        if path.hasSuffix("/households") { return response(request, 200, ["households": [household()]]) }
        if path.hasSuffix("/snapshot") { return response(request, 200, ["household_id": SharedPlanTestData.householdId.uuidString, "membership_id": membership.uuidString, "authorization_version": 1, "accounts": [], "activities": [], "positions": []]) }
        if path.hasSuffix("/plan") { return response(request, 200, ["household_id": SharedPlanTestData.householdId.uuidString, "membership_id": membership.uuidString, "authorization_version": 1, "plans": HouseholdPlanKind.allCases.map(plan)]) }
        if path.hasSuffix("/options") {
            let account: [String: Any] = ["id": Self.accountId.uuidString, "type": "cash", "nature": "asset", "currency": "DOP", "currency_fraction_digits": 2, "archived": false, "ownership_share_bps": 10000, "version": 4, "created_at": "2026-10-01T12:00:00Z", "updated_at": "2026-10-01T12:00:00Z", "balance": ["state": "unknown", "activity_since_tracking_minor": 0]]
            return response(request, 200, ["membership_id": membership.uuidString, "authorization_version": 1, "people": [SharedPlanTestData.person()], "owned_account_ids": [Self.accountId.uuidString], "money": ["accounts": [account], "eligibility": ["expense": ["cash"]], "destination_eligibility": [:], "categories": [], "sources": []], "existing_definitions": [], "purposes": ["budget": ["spending"]]])
        }
        if path.hasSuffix("/search") { return response(request, 200, ["items": [["id": SharedPlanTestData.planId.uuidString, "kind": "plan", "title": "Synthetic " + resultKind.rawValue, "account_id": NSNull(), "activity_id": NSNull(), "plan_ref": ["kind": resultKind.rawValue, "id": SharedPlanTestData.planId.uuidString]]], "next_cursor": NSNull()]) }
        for kind in HouseholdPlanKind.allCases {
            if path.hasSuffix("/plan" + HouseholdPlanRef(kind: kind, id: SharedPlanTestData.planId).path) { return response(request, 200, plan(kind)) }
        }
        return response(request, 200, household())
    }
    private func response(_ request: URLRequest, _ status: Int, _ value: [String: Any]) -> (Data, URLResponse) { (try! JSONSerialization.data(withJSONObject: value), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!) }
}

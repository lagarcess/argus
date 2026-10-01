import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class HouseholdPlanModelTests: XCTestCase {
    func testBackedSavingsUsesSupportedResidualShareAndCurrentnessFromServer() throws {
        let cases: [(String, String?, String?, String)] = [
            ("residual", "0", "4000", "active"),
            ("partial ownership", "10000", "2500", "active"),
            ("withdrawn", "10000", "0", "active"),
            ("ineligible original", "10000", nil, "needs_review")
        ]
        for (label, actual, applied, state) in cases {
            var wire = SharedPlanTestData.plan(.goal)
            var progress = try XCTUnwrap(wire["progress"] as? [String: Any])
            progress["actual_minor"] = actual as Any? ?? NSNull(); progress["applied_minor"] = applied as Any? ?? NSNull(); progress["state"] = state; wire["progress"] = progress
            let plan = try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire))
            XCTAssertEqual(HouseholdPlanPresentation.backedSavings(plan.progress.common), applied, label)
            XCTAssertEqual(plan.progress.common.state.rawValue, state, label)
        }
    }
    func testTitleOnlyEditingPreservesOriginalScheduleAndSendsNoCutoverForEveryCadence() throws {
        let schedules: [FinancialPlanSchedule] = [
            .init(cadence: .once, startDate: "2026-10-01"),
            .init(cadence: .weekly, startDate: "2026-10-01"),
            .init(cadence: .monthly, startDate: "2026-10-01", monthDays: []),
            .init(cadence: .monthly, startDate: "2026-10-15", monthDays: [1]),
            .init(cadence: .twiceMonthly, startDate: "2026-10-15", monthDays: [1, 15])
        ]
        for kind in [HouseholdPlanKind.bill, .goal, .debt] {
            for original in schedules {
                let plan = try definitionPlan(kind, schedule: original)
                let loaded = HouseholdPlanDefinitionEdit.schedule(original: original, cadence: original.cadence, startDate: original.startDate, endDate: original.endDate, secondDay: original.monthDays.last ?? 15)
                XCTAssertEqual(loaded, original)
                let patch = definitionPatch(plan, name: "Renamed", schedule: loaded)
                let wire = try JSONSerialization.jsonObject(with: JSONEncoder().encode(patch)) as! [String: Any]
                XCTAssertEqual(Set(wire.keys), ["name"], kind.rawValue + " " + original.cadence.rawValue)
            }
        }
    }
    func testFutureAmountEditsLeaveExistingAnchorsToCanonicalServer() throws {
        let original = FinancialPlanSchedule(cadence: .monthly, startDate: "2026-10-01", monthDays: [1])
        for kind in [HouseholdPlanKind.bill, .goal, .debt] {
            let plan = try definitionPlan(kind, schedule: original)
            let patch = definitionPatch(plan, amount: kind == .goal ? nil : "60.00", plannedAmount: kind == .goal ? "12.75" : nil, schedule: original)
            let wire = try JSONSerialization.jsonObject(with: JSONEncoder().encode(patch)) as! [String: Any]
            XCTAssertNil(wire["schedule"], kind.rawValue)
            XCTAssertNil(wire["name"], kind.rawValue)
            if kind == .goal {
                XCTAssertEqual(wire["planned_contribution_amount"] as? String, "12.75"); XCTAssertNil(wire["amount"])
            } else { XCTAssertEqual(wire["amount"] as? String, "60.00") }
            XCTAssertEqual(wire["effective_date"] as? String, kind == .bill ? nil : plan.definition.common.earliestEffectiveDate)
        }
    }
    func testChangedCadenceCarriesOnlyExplicitScheduleAndServerCutover() throws {
        let original = FinancialPlanSchedule(cadence: .monthly, startDate: "2026-10-01", monthDays: [1])
        let plan = try definitionPlan(.goal, schedule: original)
        let changed = HouseholdPlanDefinitionEdit.schedule(original: original, cadence: .weekly, startDate: plan.definition.common.earliestEffectiveDate, endDate: nil, secondDay: 15)
        let patch = definitionPatch(plan, schedule: changed)
        let wire = try JSONSerialization.jsonObject(with: JSONEncoder().encode(patch)) as! [String: Any]
        XCTAssertEqual(Set(wire.keys), ["schedule", "effective_date"])
        XCTAssertEqual(wire["effective_date"] as? String, plan.definition.common.earliestEffectiveDate)
        XCTAssertEqual(patch.schedule, changed)
        XCTAssertEqual(changed.monthDays, [])
    }
    private func definitionPlan(_ kind: HouseholdPlanKind, schedule: FinancialPlanSchedule) throws -> HouseholdPlan {
        var wire = SharedPlanTestData.plan(kind)
        var definition = try XCTUnwrap(wire["definition"] as? [String: Any])
        definition["schedule"] = try JSONSerialization.jsonObject(with: JSONEncoder().encode(schedule))
        definition["earliest_effective_date"] = "2026-10-16"; wire["definition"] = definition
        return try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire))
    }
    private func definitionPatch(_ plan: HouseholdPlan, name: String? = nil, amount: String? = nil, plannedAmount: String? = nil, schedule: FinancialPlanSchedule) -> HouseholdPlanDefinitionPatch {
        let digits = plan.definition.common.currencyFractionDigits
        let currentPlanned: String?
        if case .goal(_, _, _, _, let value) = plan.definition { currentPlanned = value.map { HouseholdPlanPresentation.decimal($0, digits: digits) } } else { currentPlanned = nil }
        return HouseholdPlanDefinitionEdit.patch(plan: plan, name: name ?? plan.definition.common.name, amount: amount ?? HouseholdPlanPresentation.decimal(plan.definition.amountMinor, digits: digits), plannedAmount: plannedAmount ?? currentPlanned, targetDate: nil, month: "2026-10", categories: [], uncategorized: false, schedule: schedule, effectiveDate: plan.definition.common.earliestEffectiveDate)
    }
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
    func testPeopleWritesReachCanonicalParticipantsRouteForEveryKind() async throws {
        for kind in HouseholdPlanKind.allCases {
            let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
            let plan = try XCTUnwrap(f.model.plan.plans.first { $0.ref.kind == kind })
            await f.model.plan.submit(HouseholdPlanPeopleCommand(kind: kind, scope: f.model.plan.scope(plan), participants: [], responsibilities: [], publishBudgetScope: false), action: .people(plan.ref))
            let writes = await f.server.writes
            XCTAssertEqual(writes.count, 1, kind.rawValue)
            XCTAssertEqual(writes.first?.httpMethod, "PUT", kind.rawValue)
            XCTAssertNil(f.model.pending, kind.rawValue); XCTAssertNil(f.model.errorKey, kind.rawValue)
            let commits = await f.server.commitCount(); XCTAssertEqual(commits, 1, kind.rawValue)
        }
    }
    func testCommittedConsentResponseLossReplaysExactReceiptAfterAuthorizationAdvances() async throws {
        let ref = HouseholdPlanRef(kind: .goal, id: SharedPlanTestData.planId)
        for action in [HouseholdPlanAction.create(.budget), .share(ref), .people(ref)] {
            for refreshBeforeRetry in [false, true] {
                let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
                let scope = try XCTUnwrap(f.model.plan.scope)
                await f.server.commitAndLoseNext()
                if case .create(let kind) = action {
                    let people = HouseholdPlanPeopleCommand(kind: kind, scope: scope, participants: [], responsibilities: [], publishBudgetScope: false)
                    let definition = FinancialBudgetCommand(name: "Confirmed budget", limit: "100.00", currency: "DOP", month: "2026-10", accountIds: [], categoryIds: [], includeUncategorized: true)
                    await f.model.plan.submit(HouseholdPlanCreateCommand(people: people, definition: HouseholdPlanDefinitionInput(kind: kind, value: definition)), action: action)
                } else {
                    let people = HouseholdPlanPeopleCommand(kind: ref.kind, scope: .init(membershipId: scope.membershipId, authorizationVersion: scope.authorizationVersion, planVersion: 1), participants: [], responsibilities: [], publishBudgetScope: false)
                    await f.model.plan.submit(people, action: action)
                }
                let pending = try XCTUnwrap(f.model.pending)
                XCTAssertEqual(pending.householdAuthorizationVersion, 1)
                let committed = await f.server.commitCount(); XCTAssertEqual(committed, 1)
                if refreshBeforeRetry { await f.model.foreground(); XCTAssertEqual(f.model.household?.version, 2) }
                await f.model.retry()
                let writes = await f.server.writes
                XCTAssertEqual(writes.count, 2)
                XCTAssertEqual(writes[0].httpBody, pending.body); XCTAssertEqual(writes[1].httpBody, pending.body)
                XCTAssertEqual(writes[0].value(forHTTPHeaderField: "Idempotency-Key"), writes[1].value(forHTTPHeaderField: "Idempotency-Key"))
                let total = await f.server.commitCount(); XCTAssertEqual(total, 1)
                XCTAssertNil(f.model.pending); XCTAssertNil(f.model.errorKey)
            }
        }
    }
    func testUncommittedOldAuthorizationReachesServerCASAndCannotMutate() async throws {
        let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
        let plan = try XCTUnwrap(f.model.plan.plans.first); await f.server.loseNext()
        await f.model.plan.submit(HouseholdPlanEditCommand(scope: f.model.plan.scope(plan), definition: .init(name: "Stale intention")), action: .edit(plan.ref))
        let pending = try XCTUnwrap(f.model.pending)
        await f.server.advanceAuthorization(); await f.model.foreground(); await f.model.retry()
        let writes = await f.server.writes
        XCTAssertEqual(writes.count, 2); XCTAssertEqual(writes[1].httpBody, pending.body)
        let commits = await f.server.commitCount(); XCTAssertEqual(commits, 0)
        XCTAssertNil(f.model.pending); XCTAssertEqual(f.model.errorKey, "sharedPlan.changed")
    }
    func testRetryLiveScopePreflightCannotSubmitAfterSignOutRevocationOrDisablement() async throws {
        for failure in ["signout", "household_access_unavailable", "households_unavailable"] {
            let f = try SharedPlanFixture(); _ = try await f.login(); await f.model.select(SharedPlanTestData.householdId)
            let plan = try XCTUnwrap(f.model.plan.plans.first); await f.server.loseNext()
            await f.model.plan.submit(HouseholdPlanEditCommand(scope: f.model.plan.scope(plan), definition: .init(name: "Pending intention")), action: .edit(plan.ref))
            if failure == "signout" {
                let gate = RequestGate(); await f.server.hold("scope", gate)
                let retry = Task { await f.model.retry() }
                await gate.waitUntilStarted(); _ = try await f.controller.signOut(); f.model.bind(nil)
                await gate.release(); await retry.value
            } else { await f.server.reject(failure); await f.model.retry() }
            let count = await f.server.writeCount(); XCTAssertEqual(count, 1, failure)
            XCTAssertFalse(f.model.active, failure)
        }
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
    private var loseCommitted = false
    private var isViewer = false
    private var resultKind = HouseholdPlanKind.goal
    private var membership = SharedPlanTestData.memberId
    private var authorizationVersion = 1
    private var receipts: [String: (body: Data, kind: HouseholdPlanKind)] = [:]
    private var commits = 0
    private(set) var writes: [URLRequest] = []
    func hold(_ entry: String, _ gate: RequestGate) { self.gate = (entry, gate) }
    func reject(_ code: String, count: Int = 1) { failure = code; failuresRemaining = count }
    func loseNext() { lose = true }
    func commitAndLoseNext() { loseCommitted = true }
    func advanceAuthorization() { authorizationVersion += 1 }
    func commitCount() -> Int { commits }
    func viewer() { isViewer = true }
    func searchKind(_ kind: HouseholdPlanKind) { resultKind = kind }
    func newMembership() { membership = UUID() }
    func writeCount() -> Int { writes.count }
    func household() -> [String: Any] { ["id": SharedPlanTestData.householdId.uuidString, "name": "Synthetic household", "version": authorizationVersion, "membership_id": membership.uuidString, "admin_membership_id": membership.uuidString, "members": [], "invitations": [], "shares": []] }
    func plan(_ kind: HouseholdPlanKind) -> [String: Any] {
        var value = SharedPlanTestData.plan(kind); value["membership_id"] = membership.uuidString; value["authorization_version"] = authorizationVersion
        if isViewer { value["permission"] = "view"; value["is_owner"] = false; value["contributions"] = [SharedPlanTestData.contribution()] }
        return value
    }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.hasPrefix("/api/v1/households") else { return try await auth.send(request) }
        if let failure { failuresRemaining -= 1; if failuresRemaining == 0 { self.failure = nil }; return response(request, 404, ["code": failure]) }
        if let gate, (gate.0 == "scope" && path.hasSuffix("/households/" + SharedPlanTestData.householdId.uuidString)) || (gate.0 == "snapshot" && path.hasSuffix("/plan")) || (gate.0 == "detail" && path.hasSuffix(SharedPlanTestData.planId.uuidString)) || (gate.0 == "preview" && path.hasSuffix("/preview")) { self.gate = nil; await gate.1.enter() }
        if path.hasSuffix("/preview") {
            let reviewed = FinancialActivityCommand(kind: .expense, accountId: Self.accountId, amount: "3.75", occurredAt: "2026-10-01T12:00:00Z", timeZone: "America/Santo_Domingo", note: "Canonical review", expectedVersions: [Self.accountId.uuidString: 4])
            let normalized = try JSONSerialization.jsonObject(with: JSONEncoder().encode(reviewed))
            return response(request, 200, ["plan": plan(.budget), "money": ["ready": true, "expected_versions": [Self.accountId.uuidString: 4], "affected_accounts": [], "reviewed_request": normalized, "preview_token": "review-token"]])
        }
        if request.httpMethod != "GET" {
            writes.append(request)
            if lose { lose = false; return response(request, 503, ["code": "unavailable"]) }
            let parts = path.split(separator: "/"); let kind = HouseholdPlanKind(rawValue: String(parts[5]))!
            let body = request.httpBody!; let fields = try JSONSerialization.jsonObject(with: body) as! [String: Any]
            let key = request.value(forHTTPHeaderField: "Idempotency-Key")!
            if let receipt = receipts[key] {
                guard receipt.body == body else { return response(request, 409, ["code": "idempotency_conflict"]) }
                return response(request, 200, ["plan": plan(receipt.kind), "replayed": true])
            }
            guard fields["expected_authorization_version"] as? Int == authorizationVersion else { return response(request, 409, ["code": "stale_version"]) }
            if parts.last == "participants", kind != .budget, fields["publish_budget_scope"] != nil { return response(request, 422, ["code": "plan_scope_invalid"]) }
            commits += 1; receipts[key] = (body, kind)
            if parts.count == 6 || parts.last == "share" || parts.last == "participants" { authorizationVersion += 1 }
            if loseCommitted { loseCommitted = false; return response(request, 503, ["code": "unavailable"]) }
            return response(request, 200, ["plan": plan(kind), "replayed": false])
        }
        if path.hasSuffix("/households") { return response(request, 200, ["households": [household()]]) }
        if path.hasSuffix("/snapshot") { return response(request, 200, ["household_id": SharedPlanTestData.householdId.uuidString, "membership_id": membership.uuidString, "authorization_version": authorizationVersion, "accounts": [], "activities": [], "positions": []]) }
        if path.hasSuffix("/plan") { return response(request, 200, ["household_id": SharedPlanTestData.householdId.uuidString, "membership_id": membership.uuidString, "authorization_version": authorizationVersion, "plans": HouseholdPlanKind.allCases.map(plan)]) }
        if path.hasSuffix("/options") {
            let account: [String: Any] = ["id": Self.accountId.uuidString, "type": "cash", "nature": "asset", "currency": "DOP", "currency_fraction_digits": 2, "archived": false, "ownership_share_bps": 10000, "version": 4, "created_at": "2026-10-01T12:00:00Z", "updated_at": "2026-10-01T12:00:00Z", "balance": ["state": "unknown", "activity_since_tracking_minor": 0]]
            return response(request, 200, ["membership_id": membership.uuidString, "authorization_version": authorizationVersion, "people": [SharedPlanTestData.person()], "owned_account_ids": [Self.accountId.uuidString], "money": ["accounts": [account], "eligibility": ["expense": ["cash"]], "destination_eligibility": [:], "categories": [], "sources": []], "existing_definitions": [], "purposes": ["budget": ["spending"]]])
        }
        if path.hasSuffix("/search") { return response(request, 200, ["items": [["id": SharedPlanTestData.planId.uuidString, "kind": "plan", "title": "Synthetic " + resultKind.rawValue, "account_id": NSNull(), "activity_id": NSNull(), "plan_ref": ["kind": resultKind.rawValue, "id": SharedPlanTestData.planId.uuidString]]], "next_cursor": NSNull()]) }
        for kind in HouseholdPlanKind.allCases {
            if path.hasSuffix("/plan" + HouseholdPlanRef(kind: kind, id: SharedPlanTestData.planId).path) { return response(request, 200, plan(kind)) }
        }
        return response(request, 200, household())
    }
    private func response(_ request: URLRequest, _ status: Int, _ value: [String: Any]) -> (Data, URLResponse) { (try! JSONSerialization.data(withJSONObject: value), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!) }
}

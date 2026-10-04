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
    /// Live: a removed grant or an unknown account answers `404 household_not_found` on the account
    /// route while `GET /households/{id}` still answers 200 for the same member.
    func testAnAccountRouteNotFoundNeverEndsMembershipOnItsOwn() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        await fixture.server.failNext(404, code: "household_not_found")
        await fixture.model.open(HouseholdServer.account)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        XCTAssertEqual(fixture.model.household?.id, HouseholdServer.household)
        XCTAssertNil(fixture.model.detail)
        XCTAssertEqual(fixture.model.errorKey, "household.changed")
        XCTAssertNotNil(fixture.model.snapshot)
        let paths = await fixture.server.paths
        let household = "/api/v1/households/" + HouseholdServer.household.uuidString
        let refused = try XCTUnwrap(paths.lastIndex(of: "GET " + household + "/accounts/" + HouseholdServer.account.uuidString))
        XCTAssertEqual(paths[refused + 1], "GET " + household)
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        XCTAssertEqual(reopened.selectedId, HouseholdServer.household)
    }
    func testAnAccountRouteNotFoundEndsMembershipOnlyWhenTheMembershipReadAgrees() async throws {
        for code in ["household_not_found", "not_a_member"] {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            await fixture.server.failNext(404, code: "household_not_found")
            await fixture.server.failNext(code == "not_a_member" ? 403 : 404, code: code)
            await fixture.model.open(HouseholdServer.account)
            XCTAssertNil(fixture.model.selectedId, code)
            XCTAssertEqual(fixture.model.errorKey, "household.accessEnded", code)
        }
    }
    /// Every account-scoped route answers `404 household_not_found` for a grant or account that is
    /// gone; each one re-reads the membership right after the refusal and keeps it when that read answers.
    func testAnAccountScopedNotFoundFromAnyEntryKeepsMembershipWhenTheMembershipReadAnswers() async throws {
        let household = "/api/v1/households/" + HouseholdServer.household.uuidString
        let entries: [(name: String, request: String)] = [
            ("detail", "GET " + household + "/accounts/" + HouseholdServer.account.uuidString),
            ("history", "GET " + household + "/activities/" + HouseholdServer.account.uuidString + "/history"),
            ("search", "GET " + household + "/search"),
            ("editorLoad", "GET " + household + "/activity-options"),
            ("editorReview", "POST " + household + "/activities/preview"),
            ("activityWrite", "POST " + household + "/activities"),
        ]
        for entry in entries {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            fixture.model.beginActivity(try XCTUnwrap(fixture.model.snapshot?.accounts.first))
            let editor = try XCTUnwrap(fixture.model.editor)
            editor.amount = "25"
            await fixture.server.fail(entry.request, 404, code: "household_not_found")
            switch entry.name {
            case "detail": await fixture.model.open(HouseholdServer.account)
            case "history": await fixture.model.loadHistory(HouseholdServer.account)
            case "search": await fixture.model.find("private query")
            case "editorLoad": await editor.load()
            case "editorReview": await editor.review(Locale(identifier: "en_US"))
            default:
                let household = try XCTUnwrap(fixture.model.household)
                fixture.model.editor = nil
                await fixture.model.confirmActivity(FinancialActivityCommand(kind: .expense, accountId: HouseholdServer.account, amount: "25", occurredAt: "2026-10-01T12:00:00Z", timeZone: "America/Santo_Domingo"), activityId: nil, membership: household.membershipId, version: household.version)
            }
            XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household, entry.name)
            XCTAssertEqual(fixture.model.household?.id, HouseholdServer.household, entry.name)
            XCTAssertEqual(fixture.model.errorKey, "household.changed", entry.name)
            XCTAssertNil(fixture.model.pending, entry.name)
            let paths = await fixture.server.paths
            let refused = try XCTUnwrap(paths.lastIndex(of: entry.request), entry.name)
            XCTAssertEqual(paths.dropFirst(refused + 1).first, "GET " + household, entry.name)
        }
    }
    func testAnAccountNotFoundWithoutAMembershipAnswerKeepsTheHousehold() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        let household = "/api/v1/households/" + HouseholdServer.household.uuidString
        await fixture.server.fail("GET " + household + "/accounts/" + HouseholdServer.account.uuidString, 404, code: "household_not_found")
        await fixture.server.offline("GET " + household)
        await fixture.model.open(HouseholdServer.account)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        XCTAssertEqual(fixture.model.household?.id, HouseholdServer.household)
        XCTAssertNotNil(fixture.model.snapshot)
        XCTAssertEqual(fixture.model.errorKey, "household.loadError")
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        XCTAssertEqual(reopened.selectedId, HouseholdServer.household)
    }
    /// The reload after an account refusal can end membership or lose its answer; its message stands.
    func testTheReloadAfterAnAccountRefusalKeepsItsOwnMessage() async throws {
        for (reload, expected) in [("departed", "household.accessEnded"), ("offline", "household.loadError")] {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            await fixture.server.fail("GET /api/v1/households/" + HouseholdServer.household.uuidString + "/accounts/" + HouseholdServer.account.uuidString, 404, code: "household_not_found")
            if reload == "departed" { await fixture.server.depart() } else { await fixture.server.offline("GET /api/v1/households") }
            await fixture.model.open(HouseholdServer.account)
            XCTAssertEqual(fixture.model.errorKey, expected, reload)
            XCTAssertEqual(fixture.model.selectedId == nil, reload == "departed", reload)
        }
    }
    func testANonAdminInvitationRefusalKeepsMembershipAndSaysPermissionsChanged() async throws {
        let fixture = try HouseholdFixture()
        _ = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        await fixture.server.failNext(403, code: "household_admin_required")
        await fixture.model.versionCommand("/invitations")
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        XCTAssertEqual(fixture.model.errorKey, "household.changed")
        XCTAssertNil(fixture.model.pending)
        XCTAssertNil(fixture.model.invitation)
    }
    func testScopedAccessLossClearsSelectionButOther404And403DoNot() async throws {
        for (status, code, ended) in [(403, "not_a_member", true), (404, "invitation_not_found", false), (403, "household_admin_required", false)] {
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
    func testDeniedRetryForPreviousHouseholdPreservesCurrentScope() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        let gate = RequestGate(); await fixture.server.holdInvitation(gate)
        let request = Task { await fixture.model.versionCommand("/invitations") }
        await gate.waitUntilStarted()
        await fixture.model.select(HouseholdServer.secondHousehold)
        await gate.release(); await request.value
        let pending = try XCTUnwrap(fixture.model.pending)
        XCTAssertEqual(pending.path, fixture.model.path(HouseholdServer.household, "/invitations"))
        await fixture.model.open(HouseholdServer.account)
        let currentDetail = try XCTUnwrap(fixture.model.detail?.account.account)
        let currentVersion = fixture.model.snapshot?.authorizationVersion
        await fixture.server.failNext(403, code: "not_a_member")
        await fixture.model.retry()
        XCTAssertTrue(fixture.model.active)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.secondHousehold)
        XCTAssertEqual(fixture.model.household?.id, HouseholdServer.secondHousehold)
        XCTAssertEqual(fixture.model.snapshot?.householdId, HouseholdServer.secondHousehold)
        XCTAssertEqual(fixture.model.snapshot?.authorizationVersion, currentVersion)
        XCTAssertEqual(fixture.model.detail?.account.account, currentDetail)
        XCTAssertNotEqual(fixture.model.errorKey, "household.accessEnded")
        XCTAssertNil(fixture.model.pending)
        XCTAssertNil(try fixture.journal.pending(for: identity))
        let reopened = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        reopened.bind(identity)
        XCTAssertEqual(reopened.selectedId, HouseholdServer.secondHousehold)
        await reopened.refresh()
        XCTAssertTrue(reopened.active)
    }
    func testRateLimitedPendingRetryKeepsExactCommandUntilExplicitRetry() async throws {
        let fixture = try HouseholdFixture()
        let identity = try await fixture.login()
        await fixture.server.failCreateOnce()
        await fixture.model.command(HouseholdCommand(name: "Committed once", displayName: "Alice"), path: "")
        let pending = try XCTUnwrap(fixture.model.pending)
        await fixture.server.failNext(429, code: "too_many_requests")
        await fixture.model.retry()
        XCTAssertEqual(fixture.model.pending, pending)
        XCTAssertEqual(try fixture.journal.pending(for: identity), pending)
        XCTAssertEqual(fixture.model.errorKey, "household.uncertain")
        XCTAssertTrue(fixture.model.isAvailable)
        XCTAssertFalse(fixture.model.busy)
        let beforeExplicitRetry = await fixture.server.creates
        XCTAssertEqual(beforeExplicitRetry.count, 1)
        await fixture.model.retry()
        let requests = await fixture.server.creates
        XCTAssertEqual(requests.count, 2)
        if requests.count == 2 {
            XCTAssertEqual(requests[0].httpBody, requests[1].httpBody)
            XCTAssertEqual(requests[0].value(forHTTPHeaderField: "Idempotency-Key"), requests[1].value(forHTTPHeaderField: "Idempotency-Key"))
        }
        XCTAssertNil(fixture.model.pending)
        XCTAssertNil(try fixture.journal.pending(for: identity))
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
    private var failures: [(status: Int, code: String)] = []
    private var targeted: [String: (status: Int, code: String)] = [:]
    private var unreachable: Set<String> = []
    /// Refuses the next request to exactly this method and path.
    func fail(_ request: String, _ status: Int, code: String) { targeted[request] = (status, code) }
    /// The next request to exactly this method and path gets no answer.
    func offline(_ request: String) { unreachable.insert(request) }
    private var discoveryGate: RequestGate?
    func setEnabled(_ value: Bool) { enabled = value }
    func failNext(_ status: Int, code: String) { failures.append((status, code)) }
    private(set) var paths: [String] = []
    private var previewAvailable = true
    func setPreviewAvailable(_ value: Bool) { previewAvailable = value }
    func holdDiscovery(_ gate: RequestGate) { discoveryGate = gate }
    private var version = 1
    private var active = true
    private var detailGate: RequestGate?
    private var createGate: RequestGate?
    private var failCreate = false
    private var changedAsset = false
    private var invitationGate: RequestGate?
    private(set) var creates: [URLRequest] = []
    private(set) var invitationBodies: [(path: String, body: [String: String])] = []
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
        if path.contains("household-invitations") {
            let body = (try? JSONSerialization.jsonObject(with: request.httpBody ?? Data())) as? [String: String] ?? [:]
            invitationBodies.append((path, body))
        }
        if !enabled { return response(request, 404, ["code": "households_unavailable"]) }
        let requested = request.httpMethod! + " " + path
        paths.append(requested)
        if unreachable.remove(requested) != nil { throw URLError(.notConnectedToInternet) }
        if let failure = targeted.removeValue(forKey: requested) {
            return response(request, failure.status, ["type": "https://api.argus.app/problems/" + failure.code, "status": failure.status, "code": failure.code])
        }
        if !failures.isEmpty {
            let failure = failures.removeFirst()
            return response(request, failure.status, ["type": "https://api.argus.app/problems/" + failure.code, "status": failure.status, "code": failure.code])
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
        } else if path.hasSuffix("household-invitations/accept") {
            result = receipt(householdId)
        } else if path.hasSuffix("household-invitations/preview") {
            result = ["name": "Synthetic household", "expires_at": "2026-10-08T12:00:00Z", "available": previewAvailable]
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

extension HouseholdModelTests {
    func testACodeOrALinkPreviewsAndAcceptsTheSameReviewedSecret() async throws {
        let fixture = try HouseholdFixture()
        _ = try await fixture.login()
        await fixture.model.previewInvitation(" 7k2m-9qxd-4rta ")
        XCTAssertEqual(fixture.model.invitationPreview?.name, "Synthetic household")
        await fixture.model.acceptInvitation(displayName: "Bea")
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        await fixture.model.previewInvitation("https://cuadrao.ai/invite#link-token-123456")
        let sent = await fixture.server.invitationBodies
        XCTAssertEqual(sent.map(\.path), ["/api/v1/household-invitations/preview", "/api/v1/household-invitations/accept", "/api/v1/household-invitations/preview"])
        XCTAssertEqual(sent.map(\.body), [["code": "7k2m-9qxd-4rta"], ["code": "7k2m-9qxd-4rta", "display_name": "Bea"], ["token": "link-token-123456"]])
    }

    func testPreviewOutcomesExplainTheInvitationWithoutEndingMembership() async throws {
        let cases: [(Int, String, InvitationProblem)] = [(404, "invitation_not_found", .invalid), (429, "invite_rate_limited", .rateLimited)]
        for (status, code, problem) in cases {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.select(HouseholdServer.household)
            await fixture.server.failNext(status, code: code)
            await fixture.model.previewInvitation("7K2M-9QXD-4RTA")
            XCTAssertEqual(fixture.model.invitationProblem, problem, code)
            XCTAssertNil(fixture.model.invitationPreview, code)
            XCTAssertTrue(fixture.model.isAvailable, code)
            XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household, code)
            XCTAssertNil(fixture.model.errorKey, code)
        }
    }

    func testAnExpiredUsedOrRevokedInvitationPreviewsAsUnavailable() async throws {
        let fixture = try HouseholdFixture()
        _ = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        await fixture.server.setPreviewAvailable(false)
        await fixture.model.previewInvitation("7K2M-9QXD-4RTA")
        XCTAssertEqual(fixture.model.invitationPreview?.available, false)
        XCTAssertNil(fixture.model.invitationProblem)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        XCTAssertNil(fixture.model.errorKey)
    }

    func testAcceptingAUsedOrExpiredInvitationExplainsWhyAndJoinsNothing() async throws {
        for (code, problem) in [("invitation_consumed", InvitationProblem.used), ("invitation_expired", .expired)] {
            let fixture = try HouseholdFixture()
            _ = try await fixture.login()
            await fixture.model.previewInvitation("7K2M-9QXD-4RTA")
            await fixture.server.failNext(409, code: code)
            await fixture.model.acceptInvitation(displayName: "Bea")
            XCTAssertEqual(fixture.model.invitationProblem, problem, code)
            XCTAssertNil(fixture.model.selectedId, code)
            XCTAssertNil(fixture.model.pending, code)
            XCTAssertNil(fixture.model.errorKey, code)
        }
    }

    func testUnrecognizedInputIsInvalidWithoutAnyRequest() async throws {
        let fixture = try HouseholdFixture()
        _ = try await fixture.login()
        await fixture.model.previewInvitation("https://example.com/invite#abc")
        XCTAssertEqual(fixture.model.invitationProblem, .invalid)
        let sent = await fixture.server.invitationBodies
        XCTAssertTrue(sent.isEmpty)
    }

    func testAnOpenedLinkReachesTheJoinStepOnlyWhileHouseholdsAreAvailable() async throws {
        let fixture = try HouseholdFixture()
        _ = try await fixture.login()
        await fixture.model.select(HouseholdServer.household)
        let opened = await fixture.model.beginJoin("https://cuadrao.ai/invite#link-token-123456")
        XCTAssertTrue(opened)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        let relaunched = HouseholdModel(controller: fixture.controller, configuration: fixture.configuration, journal: fixture.journal)
        relaunched.bind(fixture.model.identity)
        XCTAssertEqual(relaunched.selectedId, HouseholdServer.household)
        XCTAssertTrue(fixture.model.joiningByInvitation)
        XCTAssertTrue(fixture.model.showManagement)
        XCTAssertEqual(fixture.model.pendingInvitationToken, "https://cuadrao.ai/invite#link-token-123456")
        XCTAssertEqual(fixture.model.invitationPreview?.name, "Synthetic household")
        let previewed = await fixture.server.invitationBodies
        XCTAssertEqual(previewed.map(\.path), ["/api/v1/household-invitations/preview"])
        XCTAssertEqual(previewed.map(\.body), [["token": "link-token-123456"]])
        fixture.model.showManagement = false
        XCTAssertFalse(fixture.model.joiningByInvitation)
        XCTAssertEqual(fixture.model.selectedId, HouseholdServer.household)
        await fixture.server.setEnabled(false)
        await fixture.model.refresh()
        let refused = await fixture.model.beginJoin("7K2M-9QXD-4RTA")
        XCTAssertFalse(refused)
        XCTAssertFalse(fixture.model.showManagement)
    }
}

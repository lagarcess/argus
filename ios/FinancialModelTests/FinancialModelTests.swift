import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class FinancialModelTests: XCTestCase {
    func testDetail401RetiresSessionAndClosesAccountIdentity() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity)
        var returnedToSignIn = false
        loop.sessionChanged = { snapshot in
            accounts.bind(snapshot)
            returnedToSignIn = snapshot.phase != .authenticated
        }
        let row = try JSONDecoder().decode(FinancialActivity.self, from: Data(PresentationServer.activityRow.utf8))
        await fixture.server.expireIdentity()
        do { _ = try await loop.detail(row); XCTFail("Expired detail must fail") }
        catch { XCTAssertTrue(returnedToSignIn) }
        XCTAssertNil(accounts.identity)
    }

    func testDefinitivePendingRejectionShowsRecoveryErrorOnAccounts() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let account = try fixture.account()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity); accounts.accept(account)
        loop.record(account)
        let editor = try XCTUnwrap(loop.activityEditor)
        await editor.load(); editor.amount = "20.00"
        await editor.review(locale: Locale(identifier: "en_US"))
        await fixture.server.failNextCommit(500)
        await editor.confirm()
        XCTAssertNotNil(loop.pendingConfirmation)
        await fixture.server.failNextCommit(409)
        await loop.retryPending()
        XCTAssertNil(loop.pendingConfirmation)
        XCTAssertNotNil(loop.recoveryErrorKey)
        XCTAssertNil(try fixture.journal.pending(for: identity))
    }

    func testCanonicalConfirmedWriteSurvivesRelaunchAndCannotReachAnotherOwner() async throws {
        let fixture = try PresentationFixture()
        let alice = try await fixture.login()
        let account = try fixture.account()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(alice); loop.bind(alice); accounts.accept(account)
        loop.record(account)
        let editor = try XCTUnwrap(loop.activityEditor)
        await editor.load()
        editor.amount = "20.00"
        await editor.review(locale: Locale(identifier: "en_US"))
        XCTAssertTrue(editor.canConfirm)
        await fixture.server.failNextCommit(500)
        await editor.confirm()
        XCTAssertEqual(editor.phase, .uncertain)
        XCTAssertNotNil(loop.pendingConfirmation)
        let firstCount = await fixture.server.canonicalCommits.count
        XCTAssertEqual(firstCount, 1)

        let reopened = try fixture.reopened()
        let restored = try await reopened.restore()
        let reopenedAccounts = AccountsModel(controller: reopened)
        let reopenedJournal = FinancialWriteJournal(storage: fixture.storage, prefix: fixture.configuration.storagePrefix)
        let reopenedLoop = FinancialLoopModel(controller: reopened, accounts: reopenedAccounts, journal: reopenedJournal)
        reopenedAccounts.bind(restored); reopenedLoop.bind(restored)
        XCTAssertNotNil(reopenedLoop.pendingConfirmation)
        let reopenCount = await fixture.server.canonicalCommits.count
        XCTAssertEqual(reopenCount, 1, "Opening the app must not submit a request")

        _ = try await reopened.signOut()
        let bob = try await reopened.login(email: "bob@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
        reopenedAccounts.bind(bob); reopenedLoop.bind(bob)
        XCTAssertNil(reopenedLoop.pendingConfirmation)
        await reopenedLoop.retryPending()
        let bobCount = await fixture.server.canonicalCommits.count
        XCTAssertEqual(bobCount, 1)

        _ = try await reopened.signOut()
        let aliceAgain = try await reopened.login(email: "alice@example.test", password: "synthetic-password", captchaToken: "synthetic-captcha")
        reopenedAccounts.bind(aliceAgain); reopenedLoop.bind(aliceAgain)
        XCTAssertNotNil(reopenedLoop.pendingConfirmation)
        await reopenedLoop.retryPending()
        XCTAssertNil(reopenedLoop.pendingConfirmation)
        let commits = await fixture.server.canonicalCommits
        XCTAssertEqual(commits.count, 2)
        if commits.count == 2 {
            XCTAssertEqual(commits[0].httpBody, commits[1].httpBody)
            XCTAssertEqual(commits[0].value(forHTTPHeaderField: "Idempotency-Key"), commits[1].value(forHTTPHeaderField: "Idempotency-Key"))
        }
        XCTAssertEqual(reopenedAccounts.selected?.balance.amount, "80.00")
    }

    func testArchiveReloadAndRestorePreserveBalanceAndListPlacement() async throws {
        for unknown in [false, true] {
            let fixture = try PresentationFixture()
            await fixture.server.setUnknownBalance(unknown)
            let identity = try await fixture.login()
            let model = AccountsModel(controller: fixture.client)
            model.bind(identity)
            await model.load()
            let original = try XCTUnwrap(AccountPresentation.accounts(model.accounts, archived: false).first)
            XCTAssertTrue(AccountPresentation.accounts(model.accounts, archived: true).isEmpty)
            await model.archive(original)
            model.back()
            await model.load()
            XCTAssertTrue(AccountPresentation.accounts(model.accounts, archived: false).isEmpty)
            let archived = try XCTUnwrap(AccountPresentation.accounts(model.accounts, archived: true).first)
            XCTAssertEqual(archived.id, original.id)
            XCTAssertEqual(archived.balance, original.balance)
            XCTAssertEqual(model.accounts.count, 1, "Archiving must retain the canonical record")
            await model.open(archived)
            await model.archive(try XCTUnwrap(model.selected))
            model.back()
            await model.load()
            let restored = try XCTUnwrap(AccountPresentation.accounts(model.accounts, archived: false).first)
            XCTAssertEqual(restored.id, original.id)
            XCTAssertEqual(restored.balance, original.balance)
            XCTAssertTrue(AccountPresentation.accounts(model.accounts, archived: true).isEmpty)
            let patches = await fixture.server.archivePatches
            XCTAssertEqual(patches.count, 2)
            for request in patches {
                let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: Any])
                XCTAssertEqual(Set(payload.keys), ["archived", "expected_version"])
            }
        }
    }

    func testUncertainSaveFreezesDraftAndReplaysAcceptedOperation() async throws {
        for status in [500, 408] {
            let fixture = try PresentationFixture()
            let identity = try await fixture.login()
            var saved: FinancialAccount?
            let editor = FinancialEditor(account: try fixture.account(), kind: .expense(nil), controller: fixture.client, identity: identity) { saved = $0 }
            editor.amount = "20.00"
            await editor.review(locale: Locale(identifier: "en_US"))
            XCTAssertTrue(editor.canConfirm)
            await fixture.server.failNextCommit(status)
            await editor.confirm()
            XCTAssertEqual(editor.phase, .uncertain)
            XCTAssertFalse(editor.canEdit)
            editor.edit()
            XCTAssertEqual(editor.phase, .uncertain)
            await editor.confirm()
            XCTAssertEqual(editor.phase, .saved)
            XCTAssertEqual(saved?.balance.amount, "80.00")
            let commits = await fixture.server.commits
            XCTAssertEqual(commits.count, 2)
            XCTAssertEqual(commits[0].httpBody, commits[1].httpBody)
            XCTAssertEqual(commits[0].value(forHTTPHeaderField: "Idempotency-Key"), commits[1].value(forHTTPHeaderField: "Idempotency-Key"))
        }
    }

    func testDateChangeDropsObsoleteCoverageAndPriorAnswerCanBeCorrected() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let observation = UUID()
        let raw = #"{"record_id":"\#(UUID())","revision":1,"kind":"expense","amount_minor":2000,"amount":"20.00","balance_movement_minor":-2000,"occurred_at":"2026-09-01T12:00:00Z","time_zone":"UTC","recorded_at":"2026-09-01T12:00:00Z","coverage":[{"observation_id":"\#(observation)","included":true}]}"#
        let activity = try JSONDecoder().decode(FinancialActivity.self, from: Data(raw.utf8))
        let editor = FinancialEditor(account: try fixture.account(), kind: .expense(activity), controller: fixture.client, identity: identity) { _ in }
        editor.reason = "Date correction"
        editor.date = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-09-02T12:00:00Z"))
        await editor.review(locale: Locale(identifier: "en_US"))
        var previews = await fixture.server.previews
        var payload = try JSONDecoder().decode(ExpenseRequest.self, from: XCTUnwrap(previews.last?.httpBody))
        XCTAssertTrue(payload.coverage.isEmpty)
        editor.answer(observation, included: false)
        await editor.review(locale: Locale(identifier: "en_US"))
        previews = await fixture.server.previews
        payload = try JSONDecoder().decode(ExpenseRequest.self, from: XCTUnwrap(previews.last?.httpBody))
        XCTAssertEqual(payload.coverage, [.init(observationId: observation, included: false)])
    }

    func testExpiredIdentityDuringConfirmReturnsToSignIn() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity)
        var returnedToSignIn = false
        loop.sessionChanged = { snapshot in
            accounts.bind(snapshot)
            returnedToSignIn = snapshot.phase != .authenticated
        }
        loop.expense(try fixture.account())
        let editor = try XCTUnwrap(loop.editor)
        editor.amount = "20.00"; await editor.review(locale: Locale(identifier: "en_US"))
        await fixture.server.expireIdentity()
        await editor.confirm()
        XCTAssertTrue(returnedToSignIn)
        XCTAssertEqual(editor.phase, .retired)
        XCTAssertNil(loop.editor)
        XCTAssertNil(accounts.identity)
        XCTAssertFalse(editor.canConfirm)
    }

    func testPostSaveHomeWinsOverEarlierRead() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity); accounts.accept(try fixture.account())
        let gate = RequestGate()
        await fixture.server.holdNextHome(gate)
        let earlier = Task { await loop.refresh() }
        await gate.waitUntilStarted()
        loop.expense(try fixture.account())
        let editor = try XCTUnwrap(loop.editor)
        editor.amount = "20.00"
        await editor.review(locale: Locale(identifier: "en_US")); await editor.confirm()
        XCTAssertEqual(accounts.selected?.balance.amount, "80.00")
        XCTAssertEqual(loop.home?.currencies.first?.netWorthMinor, "8000")
        await gate.release(); await earlier.value
        XCTAssertEqual(loop.home?.currencies.first?.netWorthMinor, "8000")
    }

    func testOldEditorCannotInjectDataAfterOwnerSwitch() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity)
        loop.expense(try fixture.account())
        let editor = try XCTUnwrap(loop.editor)
        editor.amount = "20.00"; await editor.review(locale: Locale(identifier: "en_US"))
        let gate = RequestGate(); await fixture.server.holdCommit(gate)
        let saving = Task { await editor.confirm() }
        await gate.waitUntilStarted()
        _ = try await fixture.client.signOut()
        let second = try await fixture.login(email: "bob@example.test")
        accounts.bind(second); loop.bind(second)
        await gate.release(); await saving.value
        XCTAssertNil(accounts.selected)
        XCTAssertTrue(accounts.accounts.isEmpty)
        XCTAssertNil(loop.home)
        XCTAssertNil(loop.editor)
    }
}

private struct PresentationFixture {
    let server = PresentationServer()
    let client: SessionController
    let journal: FinancialWriteJournal
    let storage: MemoryStore
    let configuration: SessionConfiguration
    init() throws {
        let config = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!, supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let server = self.server
        let storage = MemoryStore()
        self.configuration = config
        self.storage = storage
        client = try SessionController(configuration: config, storage: storage, fetch: { try await server.send($0) })
        journal = FinancialWriteJournal(storage: storage, prefix: config.storagePrefix)
    }
    func reopened() throws -> SessionController {
        let server = self.server
        return try SessionController(configuration: configuration, storage: storage, fetch: { try await server.send($0) })
    }
    func login(email: String = "alice@example.test") async throws -> SessionSnapshot {
        try await client.login(email: email, password: "synthetic-password", captchaToken: "synthetic-captcha")
    }
    func account() throws -> FinancialAccount { try JSONDecoder().decode(FinancialAccount.self, from: Data(PresentationServer.account(updated: false).utf8)) }
}

private actor PresentationServer {
    let auth = AuthServer()
    static let id = UUID()
    static let activityID = UUID()
    static let cashID = UUID()
    static var activityRow: String {
        #"{"record_id":"\#(activityID)","activity_id":"\#(activityID)","revision":1,"kind":"expense","amount_minor":2000,"amount":"20.00","balance_movement_minor":-2000,"occurred_at":"2026-09-01T12:00:00Z","time_zone":"UTC","recorded_at":"2026-09-01T12:00:00Z","coverage":[]}"#
    }
    private var updated = false
    private var archived = false
    private var unknownBalance = false
    private var accountVersion = 1
    private(set) var archivePatches: [URLRequest] = []
    func setUnknownBalance(_ value: Bool) { unknownBalance = value }
    private var nextStatus: Int?
    private var expired = false
    private var homeGate: RequestGate?
    private var commitGate: RequestGate?
    private(set) var commits: [URLRequest] = []
    private(set) var canonicalCommits: [URLRequest] = []
    private(set) var previews: [URLRequest] = []
    func expireIdentity() { expired = true }
    func failNextCommit(_ status: Int) { nextStatus = status }
    func holdNextHome(_ gate: RequestGate) { homeGate = gate }
    func holdCommit(_ gate: RequestGate) { commitGate = gate }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.contains("/financial-") else { return try await auth.send(request) }
        if path.contains("/financial-plan") { return try await plan(request) }
        if path.contains("/financial-activities") {
            return try canonical(request)
        }
        var status = 200
        let body: String
        if request.httpMethod == "PATCH", path.hasSuffix(Self.id.uuidString) {
            let payload = try JSONSerialization.jsonObject(with: request.httpBody!) as! [String: Any]
            archived = payload["archived"] as! Bool
            accountVersion += 1
            archivePatches.append(request)
            body = accountRecord()
        } else if path.hasSuffix("/financial-accounts") {
            body = "{\"accounts\":[" + accountRecord() + "]}"
        } else if path.hasSuffix(Self.id.uuidString), request.httpMethod == "GET" {
            body = accountRecord()
        } else if path.hasSuffix("/financial-home") {
            let amount = updated ? "8000" : "10000"
            body = #"{"currencies":[{"currency":"DOP","currency_fraction_digits":2,"assets_minor":"\#(amount)","cash_minor":"\#(amount)","other_assets_minor":"0","debts_minor":"0","net_worth_minor":"\#(amount)","recorded_spending_minor":"2000","known_accounts":1,"unknown_accounts":0,"as_of":null}],"recent_activity":[],"recorded_at":"2026-09-01T12:00:00Z"}"#
            if let gate = homeGate { homeGate = nil; await gate.enter() }
        } else if path.hasSuffix("/preview") {
            previews.append(request)
            body = #"{"account_version":1,"ready":true,"observations":[],"before":\#(Self.balance(false)),"after":\#(Self.balance(true)),"preview_token":"reviewed"}"#
        } else if request.httpMethod == "POST" {
            commits.append(request); updated = true
            if let gate = commitGate { commitGate = nil; await gate.enter() }
            status = expired ? 401 : nextStatus ?? 200; nextStatus = nil
            body = #"{"account":\#(Self.account(updated:true)),"activity":{"record_id":"\#(Self.activityID)","revision":1,"kind":"expense","amount_minor":2000,"amount":"20.00","balance_movement_minor":-2000,"occurred_at":"2026-09-01T12:00:00Z","time_zone":"UTC","recorded_at":"2026-09-01T12:00:00Z","coverage":[]},"replayed":true}"#
        } else { body = #"{"items":[],"next_cursor":null}"# }
        return (Data(body.utf8), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
    static let expectationId = UUID()
    private(set) var planCommits: [URLRequest] = []
    static var expectation: String {
        #"{"id":"\#(expectationId)","version":1,"kind":"bill","title":"Synthetic rent","currency":"DOP","currency_fraction_digits":2,"amount_minor":2000,"amount":"20.00","account_id":"\#(id)","schedule":{"cadence":"monthly","start_date":"2026-01-31","end_date":null,"month_days":[]},"archived":false,"earliest_effective_date":"2026-09-29"}"#
    }
    static func planProjection(updated: Bool) -> String {
        let amount = updated ? "8000" : "10000"
        let home = #"{"currencies":[{"currency":"DOP","currency_fraction_digits":2,"assets_minor":"\#(amount)","cash_minor":"\#(amount)","other_assets_minor":"0","debts_minor":"0","net_worth_minor":"\#(amount)","recorded_spending_minor":"2000","known_accounts":1,"unknown_accounts":0,"as_of":null}],"recent_activity":[],"recorded_at":"2026-09-01T12:00:00Z"}"#
        return #"{"home":\#(home),"selection":{"version":0,"account_ids":[],"time_zone":"America/Santo_Domingo"},"accounts":[\#(account(updated:false))],"expectations":[\#(expectation)],"occurrences":[],"currencies":[],"start_date":"2026-09-29","end_date":"2026-10-29","coverage":"recorded_and_expected","has_expectations":true}"#
    }
    private func plan(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let body: String
        var status = 200
        if request.httpMethod == "GET" {
            body = Self.planProjection(updated: updated)
            if let gate = homeGate { homeGate = nil; await gate.enter() }
        }
        else {
            planCommits.append(request)
            status = nextStatus ?? 200; nextStatus = nil
            if request.url!.path.hasSuffix("/selection") {
                body = #"{"selection":{"version":1,"account_ids":[],"time_zone":"America/Santo_Domingo"},"replayed":true}"#
            } else { body = #"{"expectation":\#(Self.expectation),"replayed":true}"# }
        }
        return (Data(body.utf8), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }

    private func canonical(_ request: URLRequest) throws -> (Data, URLResponse) {
        let path = request.url!.path
        let body: String
        var status = 200
        if expired, request.httpMethod == "GET" {
            status = 401
            body = #"{"code":"unauthorized"}"#
        } else if path.hasSuffix("/options") {
            let cash = Self.account(updated: false)
                .replacingOccurrences(of: Self.id.uuidString, with: Self.cashID.uuidString)
                .replacingOccurrences(of: "\"type\":\"checking\"", with: "\"type\":\"cash\"")
            body = #"{"accounts":[\#(accountRecord()),\#(cash)],"eligibility":{"expense":["cash","checking","savings","credit_card"],"income":["cash","checking","savings","investment"],"transfer":["cash","checking","savings","investment"],"card_payment":["cash","checking","savings","investment"],"refund":["cash","checking","savings","credit_card"]},"destination_eligibility":{"transfer":["cash","checking","savings","investment"],"card_payment":["credit_card"]},"categories":["groceries"],"sources":["salary"]}"#
        } else if path.hasSuffix("/purchases") {
            body = #"{"items":[]}"#
        } else if path.hasSuffix("/preview") {
            let payload = try JSONSerialization.jsonObject(with: request.httpBody!) as! [String: Any]
            let ids = [payload["account_id"], payload["source_account_id"], payload["destination_account_id"]]
                .compactMap { $0 as? String }
            let effects = ids.map { id in
                #"{"account_id":"\#(id)","currency":"DOP","currency_fraction_digits":2,"before":\#(Self.balance(false)),"after":\#(Self.balance(true)),"observations":[],"unexplained_before":{},"unexplained_after":{}}"#
            }.joined(separator: ",")
            let reviewed = String(data: try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]), encoding: .utf8)!
            body = #"{"ready":true,"expected_versions":{},"affected_accounts":[\#(effects)],"reviewed_request":\#(reviewed),"preview_token":"reviewed"}"#
        } else if request.httpMethod == "POST" || request.httpMethod == "PATCH" {
            canonicalCommits.append(request)
            status = nextStatus ?? 200; nextStatus = nil
            if status == 200 || status >= 500 { updated = true }
            let payload = try JSONSerialization.jsonObject(with: request.httpBody!) as! [String: Any]
            let kind = payload["kind"] as? String ?? "expense"
            let accountID = payload["account_id"] as? String ?? Self.id.uuidString
            let date = payload["occurred_at"] as? String ?? "2026-09-01T12:00:00Z"
            let zone = payload["time_zone"] as? String ?? "UTC"
            let activity = #"{"activity_id":"\#(Self.activityID)","revision":1,"kind":"\#(kind)","amount_minor":2000,"amount":"20.00","currency":"DOP","currency_fraction_digits":2,"occurred_at":"\#(date)","time_zone":"\#(zone)","note":null,"category_id":null,"source_id":null,"purchase_activity_id":null,"purchase_revision":null,"reason":null,"recorded_at":"2026-09-01T12:00:00Z","recorded_by":null,"legs":[{"record_id":"\#(Self.activityID)","record_revision":1,"account_id":"\#(accountID)","role":"single","balance_movement_minor":-2000,"coverage":[]}]}"#
            body = #"{"activity":\#(activity),"accounts":[\#(Self.account(updated: true))],"replayed":\#(canonicalCommits.count > 1)}"#
        } else {
            body = #"{"items":[],"next_cursor":null}"#
        }
        return (Data(body.utf8), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
    private func accountRecord() -> String {
        var record = Self.account(updated: updated)
            .replacingOccurrences(of: "\"archived\":false", with: "\"archived\":\(archived)")
            .replacingOccurrences(of: "\"version\":1", with: "\"version\":\(accountVersion)")
        if unknownBalance {
            record = record.replacingOccurrences(of: Self.balance(updated), with: #"{"state":"unknown","amount_minor":null,"amount":null,"as_of":null,"basis":null,"activity_since_tracking_minor":0}"#)
        }
        return record
    }
    static func balance(_ updated: Bool) -> String {
        #"{"state":"known","amount_minor":\#(updated ? 8000 : 10000),"amount":"\#(updated ? "80.00" : "100.00")","as_of":"2026-09-01T12:00:00Z","basis":"opening","activity_since_tracking_minor":\#(updated ? -2000 : 0)}"#
    }
    static func account(updated: Bool) -> String {
        #"{"id":"\#(id)","type":"checking","nature":"asset","currency":"DOP","currency_fraction_digits":2,"nickname":"Synthetic","archived":false,"ownership_share_bps":10000,"version":\#(updated ? 2 : 1),"created_at":"2026-09-01T12:00:00Z","updated_at":"2026-09-01T12:00:00Z","balance":\#(balance(updated)),"opening":null}"#
    }
}

@MainActor
extension FinancialModelTests {
    func testPlanTitleAndAmountEditDoesNotRewritePastSchedule() throws {
        let expectation = try JSONDecoder().decode(FinancialExpectation.self, from: Data(PresentationServer.expectation.utf8))
        let draft = FinancialExpectationDraft(expectation: expectation)
        draft.title = "Revised rent"; draft.amount = "25.50"
        XCTAssertFalse(draft.structuralChange)
        let command = try draft.command(locale: Locale(identifier: "en_US"))
        let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(command)) as? [String: Any])
        XCTAssertNil(payload["schedule"])
        XCTAssertNil(payload["effective_date"])
        XCTAssertNil(payload["kind"])
        XCTAssertNil(payload["account_id"], "Omitting an unchanged account preserves pending occurrence identity")
        XCTAssertEqual(payload["amount"] as? String, "25.50")
        XCTAssertEqual(payload["expected_version"] as? Int, expectation.version)
        draft.accountId = nil
        XCTAssertTrue(draft.structuralChange)
        let moved = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(draft.command(locale: Locale(identifier: "en_US")))) as? [String: Any])
        XCTAssertNil(moved["schedule"], "An account-only edit must let the server choose the next safe scheduled date")
        XCTAssertTrue(moved["account_id"] is NSNull)
        XCTAssertEqual(moved["effective_date"] as? String, expectation.earliestEffectiveDate)
    }

    func testPlanConfirmationSurvivesRelaunchAndDifferentOwnerCannotReplay() async throws {
        let fixture = try PresentationFixture()
        let alice = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(alice); loop.bind(alice)
        await loop.plan.refresh()
        XCTAssertNotNil(loop.plan.projection)
        loop.plan.create()
        let draft = try XCTUnwrap(loop.plan.draft)
        draft.title = "Test bill"; draft.amount = "12.34"
        await fixture.server.failNextCommit(500)
        await loop.plan.save(locale: Locale(identifier: "en_US"))
        let pending = try XCTUnwrap(loop.pendingConfirmation)
        XCTAssertEqual(pending.planOperation, .createExpectation)
        XCTAssertNotNil(try fixture.journal.pending(for: alice))
        let reopened = try fixture.reopened()
        let restored = try await reopened.restore()
        let reopenedAccounts = AccountsModel(controller: reopened)
        let reopenedLoop = FinancialLoopModel(controller: reopened, accounts: reopenedAccounts, journal: fixture.journal)
        reopenedAccounts.bind(restored); reopenedLoop.bind(restored)
        XCTAssertEqual(reopenedLoop.pendingConfirmation, pending)
        let beforeRetry = await fixture.server.planCommits.count
        XCTAssertEqual(beforeRetry, 1)
        _ = try await reopened.signOut()
        let bob = try await reopened.login(email: "bob@example.test", password: "synthetic", captchaToken: "synthetic")
        reopenedAccounts.bind(bob); reopenedLoop.bind(bob)
        XCTAssertNil(reopenedLoop.plan.projection)
        XCTAssertNil(reopenedLoop.plan.draft)
        XCTAssertNil(reopenedLoop.pendingConfirmation)
        await reopenedLoop.retryPending()
        let bobCount = await fixture.server.planCommits.count
        XCTAssertEqual(bobCount, 1)
        _ = try await reopened.signOut()
        let aliceAgain = try await reopened.login(email: "alice@example.test", password: "synthetic", captchaToken: "synthetic")
        reopenedAccounts.bind(aliceAgain); reopenedLoop.bind(aliceAgain)
        await reopenedLoop.retryPending()
        XCTAssertNil(reopenedLoop.pendingConfirmation)
        XCTAssertNotNil(reopenedLoop.home)
        XCTAssertNotNil(reopenedLoop.plan.projection)
        XCTAssertEqual(reopenedLoop.home?.currencies.first?.netWorthMinor,
                       reopenedLoop.plan.projection?.home.currencies.first?.netWorthMinor)
        let commits = await fixture.server.planCommits
        XCTAssertEqual(commits.count, 2)
        XCTAssertEqual(commits.first?.httpBody, commits.last?.httpBody)
        XCTAssertEqual(commits.first?.value(forHTTPHeaderField: "Idempotency-Key"), commits.last?.value(forHTTPHeaderField: "Idempotency-Key"))
    }

    func testEmptyPlanSelectionIsAnExplicitJournaledPut() async throws {
        let fixture = try PresentationFixture()
        let identity = try await fixture.login()
        let accounts = AccountsModel(controller: fixture.client)
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts, journal: fixture.journal)
        accounts.bind(identity); loop.bind(identity)
        await loop.plan.refresh()
        await fixture.server.failNextCommit(500)
        let saved = await loop.plan.selectAccounts([], timeZone: "America/Santo_Domingo")
        XCTAssertFalse(saved)
        let pending = try XCTUnwrap(loop.pendingConfirmation)
        XCTAssertEqual(pending.method, "PUT")
        XCTAssertEqual(pending.planOperation, .selection(version: 0))
        let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: pending.body) as? [String: Any])
        XCTAssertEqual(payload["account_ids"] as? [String], [])
        await loop.retryPending()
        XCTAssertNil(loop.pendingConfirmation)
        let commits = await fixture.server.planCommits
        XCTAssertEqual(commits.first?.httpBody, commits.last?.httpBody)
    }
}

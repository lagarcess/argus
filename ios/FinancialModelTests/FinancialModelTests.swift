import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class FinancialModelTests: XCTestCase {
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
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts)
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
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts)
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
        let loop = FinancialLoopModel(controller: fixture.client, accounts: accounts)
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
    init() throws {
        let config = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!, supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let server = self.server
        client = try SessionController(configuration: config, storage: MemoryStore(), fetch: { try await server.send($0) })
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
    private(set) var previews: [URLRequest] = []
    func expireIdentity() { expired = true }
    func failNextCommit(_ status: Int) { nextStatus = status }
    func holdNextHome(_ gate: RequestGate) { homeGate = gate }
    func holdCommit(_ gate: RequestGate) { commitGate = gate }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.contains("/financial-") else { return try await auth.send(request) }
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

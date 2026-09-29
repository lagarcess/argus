import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class FinancialModelTests: XCTestCase {
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
    private var nextStatus: Int?
    private var homeGate: RequestGate?
    private var commitGate: RequestGate?
    private(set) var commits: [URLRequest] = []
    func failNextCommit(_ status: Int) { nextStatus = status }
    func holdNextHome(_ gate: RequestGate) { homeGate = gate }
    func holdCommit(_ gate: RequestGate) { commitGate = gate }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        let path = request.url!.path
        guard path.contains("/financial-") else { return try await auth.send(request) }
        var status = 200
        let body: String
        if path.hasSuffix("/financial-home") {
            let amount = updated ? "8000" : "10000"
            body = #"{"currencies":[{"currency":"DOP","currency_fraction_digits":2,"assets_minor":"\#(amount)","cash_minor":"\#(amount)","other_assets_minor":"0","debts_minor":"0","net_worth_minor":"\#(amount)","recorded_spending_minor":"2000","known_accounts":1,"unknown_accounts":0,"as_of":null}],"recent_activity":[],"recorded_at":"2026-09-01T12:00:00Z"}"#
            if let gate = homeGate { homeGate = nil; await gate.enter() }
        } else if path.hasSuffix("/preview") {
            body = #"{"account_version":1,"ready":true,"observations":[],"before":\#(Self.balance(false)),"after":\#(Self.balance(true)),"preview_token":"reviewed"}"#
        } else if request.httpMethod == "POST" {
            commits.append(request); updated = true
            if let gate = commitGate { commitGate = nil; await gate.enter() }
            status = nextStatus ?? 200; nextStatus = nil
            body = #"{"account":\#(Self.account(updated:true)),"activity":{"record_id":"\#(Self.activityID)","revision":1,"kind":"expense","amount_minor":2000,"amount":"20.00","balance_movement_minor":-2000,"occurred_at":"2026-09-01T12:00:00Z","time_zone":"UTC","recorded_at":"2026-09-01T12:00:00Z","coverage":[]},"replayed":true}"#
        } else { body = #"{"items":[],"next_cursor":null}"# }
        return (Data(body.utf8), HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }
    static func balance(_ updated: Bool) -> String {
        #"{"state":"known","amount_minor":\#(updated ? 8000 : 10000),"amount":"\#(updated ? "80.00" : "100.00")","as_of":"2026-09-01T12:00:00Z","basis":"opening","activity_since_tracking_minor":\#(updated ? -2000 : 0)}"#
    }
    static func account(updated: Bool) -> String {
        #"{"id":"\#(id)","type":"checking","nature":"asset","currency":"DOP","currency_fraction_digits":2,"nickname":"Synthetic","archived":false,"ownership_share_bps":10000,"version":\#(updated ? 2 : 1),"created_at":"2026-09-01T12:00:00Z","updated_at":"2026-09-01T12:00:00Z","balance":\#(balance(updated)),"opening":null}"#
    }
}

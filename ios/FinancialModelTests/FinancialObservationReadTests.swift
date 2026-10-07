import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels
@MainActor
final class FinancialObservationReadTests: XCTestCase {
    private let facts = ObservationFacts()

    func testAcceptedCorrectionsKeepRawAmountsAndCurrentMetadata() throws {
        let cases: [(String, Int, String, Int64, Int64)] = [("USD", 2, "credit_card", -1200, 0), ("JPY", 0, "checking", 0, -1200), ("KWD", 3, "property", 1200, 0)]
        for (currency, digits, type, firstAmount, lastAmount) in cases {
            let kind = type == "property" ? "value_update" : "balance_check"
            var opening = facts.fact(firstAmount, kind: "opening", revision: 2, digits: digits)
            opening["revisions"] = [facts.fact(firstAmount / 2, kind: "opening", digits: digits), opening]
            var check = facts.fact(lastAmount, at: ObservationFacts.inside, kind: kind, revision: 3, digits: digits)
            check["revisions"] = [facts.fact(80, kind: kind, digits: digits), check]
            let account = facts.account(opening: opening, estimates: [opening, check], currency: currency, digits: digits, type: type)
            let value = try complete(facts.read(account, checks: [check]))
            XCTAssertEqual(value.observations.map(\.amountMinor), [firstAmount, lastAmount])
            XCTAssertEqual(value.observations.map(\.revision), [2, 3])
            XCTAssertEqual(value.observations.map(\.kind.rawValue), ["opening", kind])
            XCTAssertEqual(value.observations.last?.asOf, check["as_of"] as? String)
            XCTAssertEqual(value.observations.last?.recordedAt, check["recorded_at"] as? String)
            XCTAssertEqual(value.observations.last?.timeZone, "America/Santo_Domingo")
            XCTAssertEqual(value.currency, currency); XCTAssertEqual(value.currencyFractionDigits, digits)
            XCTAssertEqual(value.currentMetadata.type, type); XCTAssertTrue(value.currentMetadata.archived)
            XCTAssertEqual(value.currentMetadata.ownershipShareBps, 2500)
            XCTAssertEqual(value.currentMetadata.nickname, account["nickname"] as? String)
            XCTAssertEqual(value.currentMetadata.updatedAt, account["updated_at"] as? String)
            guard case .pair(_, _, .periodStart, .minor(let change)) = value.selection else { return XCTFail("Expected raw change") }
            XCTAssertEqual(change, lastAmount - firstAmount)
        }
    }

    func testPeriodSelectionKeepsMissingSinglePartialAndPriorFactsDistinct() throws {
        let prior = facts.fact(100, at: "2026-08-31T23:00:00-04:00")
        let inside = facts.fact(150, at: ObservationFacts.inside)
        let later = facts.fact(220, at: "2026-09-20T12:00:00-04:00")
        let end = facts.fact(500, at: ObservationFacts.end)
        let cases: [([[String: Any]], [Int64], PersonalAccountObservations.Baseline?)] = [
            ([], [], nil), ([end], [], nil), ([inside], [150], .partialBaseline),
            ([prior], [100], .periodStart), ([inside, prior], [100, 150, 50], .periodStart),
            ([later, inside], [150, 220, 70], .partialBaseline), ([end, inside, prior], [100, 150, 50], .periodStart),
        ]
        for (checks, expected, expectedBaseline) in cases {
            let value = try complete(facts.read(facts.account(latest: checks.first), checks: checks))
            XCTAssertEqual(value.period, facts.period)
            switch value.selection {
            case .none: XCTAssertEqual(expected, [])
            case .unavailableOrder: XCTFail("Monotonic reviews must remain comparable")
            case let .single(fact, baseline):
                XCTAssertEqual([fact.amountMinor], expected); XCTAssertEqual(baseline, expectedBaseline)
                XCTAssertEqual(fact.asOf, checks[0]["as_of"] as? String)
            case let .pair(opening, closing, baseline, delta):
                guard case .minor(let amount) = delta else { return XCTFail("Expected checked difference") }
                XCTAssertEqual([opening.amountMinor, closing.amountMinor, amount], expected)
                XCTAssertEqual(baseline, expectedBaseline)
                XCTAssertLessThan(closing.instant, try XCTUnwrap(AccountPresentation.parseDate(ObservationFacts.end)))
            }
        }
    }

    func testBackwardClockOrderKeepsRawFactsButWithholdsComparison() throws {
        let opening = facts.fact(10000, at: "2026-08-01T00:00:00-04:00", kind: "opening")
        let older = facts.fact(9000, at: "2026-09-02T12:00:00-04:00")
        let newer = facts.fact(8000, at: "2026-09-02T08:00:00-04:00")
        let account = facts.account(opening: opening, latest: newer)
        let value = try complete(facts.read(account, checks: [newer, older]))
        XCTAssertEqual(value.selection, .unavailableOrder)
        XCTAssertEqual(value.observations.map(\.amountMinor), [10000, 8000, 9000])
        XCTAssertEqual(value.observations.map(\.reviewOrder), [0, 2, 1])
        XCTAssertEqual(value.observations.map(\.asOf), [opening, newer, older].map { $0["as_of"] as! String })
        let august = FinancialHomePeriod(month: "2026-08", timeZone: facts.period.timeZone, startAt: "2026-08-01T00:00:00-04:00", endAtExclusive: ObservationFacts.start)
        let earlier = try complete(facts.read(account, checks: [newer, older], period: august))
        guard case .single(let fact, .periodStart) = earlier.selection else { return XCTFail("Later conflict must not change August") }
        XCTAssertEqual(fact.amountMinor, 10000)
    }

    func testOverflowAndInvalidFactsCannotProduceAComparison() throws {
        for (opening, closing) in [(Int64.min, Int64.max), (Int64.max, Int64.min)] {
            let check = facts.fact(closing, at: ObservationFacts.inside)
            let value = try complete(facts.read(facts.account(opening: facts.fact(opening, kind: "opening"), latest: check), checks: [check]))
            guard case .pair(_, _, _, .unavailableOverflow) = value.selection else { return XCTFail("Overflow must stay unavailable") }
        }
        for (key, value) in [("as_of", "invalid" as Any), ("recorded_at", "invalid"), ("revision", 0), ("kind", "expense")] {
            var check = facts.fact(10); check[key] = value
            XCTAssertEqual(try facts.read(facts.account(), checks: [check]), .unavailable)
        }
        let duplicate = facts.fact(10)
        XCTAssertEqual(try facts.read(facts.account(), checks: [duplicate, duplicate]), .unavailable)
        for start in ["invalid", ObservationFacts.end] {
            var period = facts.period; period.startAt = start
            XCTAssertEqual(try facts.read(facts.account(), period: period), .unavailable)
        }
    }

    func testCompletePagesKeepEqualInstantReviewOrderAndDoNotPublishState() async throws {
        let opening = facts.fact(0, kind: "opening")
        let older = facts.fact(10)
        var newer = facts.fact(20, at: "2026-09-01T04:00:00.000Z")
        newer["recorded_at"] = "2026-09-02T12:00:00Z"
        let account = facts.account(opening: opening, latest: newer)
        let fixture = try await ObservationSession([
            ObservationReply(account), ObservationReply(facts.page([newer], cursor: "older")),
            ObservationReply(facts.page([older])), ObservationReply(account),
        ])
        let value = try complete(await fixture.loop.observations(accountID: facts.id, period: facts.period))
        XCTAssertEqual(value.observations.map(\.recordID.uuidString), [opening, older, newer].map { $0["record_id"] as! String })
        XCTAssertEqual(value.observations.map(\.reviewOrder), [0, 1, 2])
        guard case .single(let selected, .periodStart) = value.selection else { return XCTFail("Latest tie is the boundary fact") }
        XCTAssertEqual(selected.amountMinor, 20)
        XCTAssertTrue(fixture.loop.accounts.accounts.isEmpty); XCTAssertTrue(fixture.loop.accountReads.isEmpty)
        let requests = await fixture.server.requests
        XCTAssertEqual(requests.map(\.httpMethod), Array(repeating: "GET", count: 4))
        XCTAssertEqual(requests.map { $0.url!.path }, ["", "/balance-checks", "/balance-checks", ""].map { "/api/v1/financial-accounts/" + facts.id.uuidString + $0 })
        XCTAssertEqual(requests[2].url?.query, "cursor=older")
    }

    func testBracketMismatchAndIncompleteReadsReturnNoData() async throws {
        let account = facts.account(opening: facts.fact(100, kind: "opening"))
        let first = try ObservationReply(account), page = try ObservationReply(facts.page([facts.fact(200)]))
        let next = try ObservationReply(facts.page([facts.fact(300)], cursor: "next"))
        var cases: [([ObservationReply], PersonalObservationRead)] = []
        for status in [403, 404, 503] { cases.append(([try ObservationReply(account, status: status)], .unavailable)) }
        for prefix in [[first], [first, next]] {
            cases.append((prefix + [try ObservationReply(["code": "stale_cursor"], status: 409)], .stale))
            cases.append((prefix + [try ObservationReply([:], status: 503)], .incomplete(.pageFailure)))
        }
        cases.append(([first, page, try ObservationReply([:], status: 503)], .incomplete(.verificationFailure)))
        for (key, value) in [("id", UUID().uuidString as Any), ("version", 5), ("currency", "EUR"), ("currency_fraction_digits", 0)] {
            var changed = account; changed[key] = value
            cases.append(([first, page, try ObservationReply(changed)], .stale))
            if key == "id" { cases.append(([try ObservationReply(changed)], .stale)) }
        }
        cases.append(([first, next, next], .incomplete(.repeatedCursor)))
        let capped = try (0..<64).map { try ObservationReply(facts.page([], cursor: "page-\($0)")) }
        cases.append(([first] + capped, .incomplete(.pageLimit)))
        for (replies, expected) in cases {
            let fixture = try await ObservationSession(replies)
            let result = await fixture.loop.observations(accountID: facts.id, period: facts.period)
            XCTAssertEqual(result, expected)
            let count = await fixture.server.requests.count; XCTAssertEqual(count, replies.count)
        }
        let fixture = try await ObservationSession([first] + Array(capped.dropLast()) + [page, first])
        _ = try complete(await fixture.loop.observations(accountID: facts.id, period: facts.period))
    }

    func testHeldReadsRetireOnCancellationSignOutOwnerSwitchOrRebind() async throws {
        let account = facts.account(opening: facts.fact(100, kind: "opening"))
        for stage in 0..<3 {
            for transition in ["cancel", "signOut", "ownerSwitch", "rebind"] {
                let gate = RequestGate()
                var replies = try [ObservationReply(account), ObservationReply(facts.page([facts.fact(200)])), ObservationReply(account)]
                replies[stage].gate = gate; replies[stage].interrupted = transition == "cancel"
                let fixture = try await ObservationSession(replies)
                var retired: SessionSnapshot?
                fixture.loop.sessionChanged = { retired = $0 }
                let reading = Task { await fixture.loop.observations(accountID: facts.id, period: facts.period) }
                await gate.waitUntilStarted()
                switch transition {
                case "cancel": reading.cancel()
                case "rebind": fixture.loop.bind(nil)
                default:
                    _ = try await fixture.client.signOut()
                    if transition == "ownerSwitch" { _ = try await fixture.client.login(email: "bob@example.test", password: "test", captchaToken: "test") }
                }
                await gate.release()
                let result = await reading.value; XCTAssertEqual(result, transition == "cancel" ? .cancelled : .stale)
                let count = await fixture.server.requests.count; XCTAssertEqual(count, stage + 1)
                if transition == "signOut" || transition == "ownerSwitch" {
                    let current = await fixture.client.snapshot(); XCTAssertEqual(retired, current)
                }
            }
        }
        let fixture = try await ObservationSession([])
        let reading = Task { await fixture.loop.observations(accountID: facts.id, period: facts.period) }
        reading.cancel()
        let result = await reading.value; XCTAssertEqual(result, .cancelled)
        let requests = await fixture.server.requests; XCTAssertTrue(requests.isEmpty)
    }

    private func complete(_ read: PersonalObservationRead, file: StaticString = #filePath, line: UInt = #line) throws -> PersonalAccountObservations {
        guard case .complete(let value) = read else { XCTFail("Expected complete read, got \(read)", file: file, line: line); throw SessionFailure.invalidResponse }
        return value
    }
}
@MainActor
private struct ObservationFacts {
    static let start = "2026-09-01T00:00:00-04:00", inside = "2026-09-12T12:00:00-04:00", end = "2026-10-01T00:00:00-04:00"
    let id = UUID()
    var period: FinancialHomePeriod { .init(month: "2026-09", timeZone: "America/Santo_Domingo", startAt: Self.start, endAtExclusive: Self.end) }
    func fact(_ amount: Int64, at: String = ObservationFacts.start, kind: String = "balance_check", revision: Int = 1, digits: Int = 2) -> [String: Any] {
        ["record_id": UUID().uuidString, "revision": revision, "kind": kind, "amount_minor": amount,
         "observed_amount_minor": amount, "amount": AccountPresentation.decimal(amount, digits: digits), "as_of": at,
         "time_zone": "America/Santo_Domingo", "recorded_at": "2026-10-02T12:00:00Z", "source": "manual", "revisions": []]
    }
    func account(opening: [String: Any]? = nil, estimates: [[String: Any]] = [], currency: String = "USD", digits: Int = 2, type: String = "checking", latest: [String: Any]? = nil) -> [String: Any] {
        let latest = latest ?? estimates.last ?? opening
        return ["id": id.uuidString, "type": type, "nature": type == "credit_card" ? "liability" : "asset", "currency": currency, "currency_fraction_digits": digits,
            "nickname": "Account " + id.uuidString, "archived": true, "ownership_share_bps": 2500, "version": 4,
            "created_at": Self.start, "updated_at": "2026-10-02T12:00:00Z", "opening": opening as Any? ?? NSNull(),
            "balance": ["state": latest == nil ? "unknown" : "known", "amount_minor": latest?["amount_minor"] ?? NSNull(),
                "amount": latest?["amount"] ?? NSNull(), "as_of": latest?["as_of"] ?? NSNull(), "activity_since_tracking_minor": 0],
            "asset": type == "property" ? ["estimates": estimates, "current_estimate": latest as Any? ?? NSNull(), "changes": []] : NSNull()]
    }
    func page(_ checks: [[String: Any]], cursor: String? = nil) -> [String: Any] { ["items": checks, "next_cursor": cursor as Any? ?? NSNull()] }
    func read(_ account: [String: Any], checks: [[String: Any]] = [], period: FinancialHomePeriod? = nil) throws -> PersonalObservationRead {
        let value = try JSONDecoder().decode(FinancialAccount.self, from: JSONSerialization.data(withJSONObject: account))
        let checks = try JSONDecoder().decode([FinancialCheck].self, from: JSONSerialization.data(withJSONObject: checks))
        return PersonalAccountObservations.accepted(requestedID: id, before: value, checksInServerOrder: checks, after: value, period: period ?? self.period)
    }
}
private struct ObservationReply: Sendable {
    let data: Data
    var status: Int
    var gate: RequestGate?
    var interrupted = false
    init(_ body: Any, status: Int = 200) throws { data = try JSONSerialization.data(withJSONObject: body); self.status = status }
}
private actor ObservationServer {
    let auth = AuthServer()
    private var replies: [ObservationReply]
    private(set) var requests: [URLRequest] = []
    init(_ replies: [ObservationReply]) { self.replies = replies }
    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        guard request.url!.path.contains("/financial-") else { return try await auth.send(request) }
        requests.append(request)
        guard !replies.isEmpty else { throw SessionFailure.invalidResponse }
        let reply = replies.removeFirst()
        if let gate = reply.gate { await gate.enter() }
        if reply.interrupted { throw URLError(.cancelled) }
        return (reply.data, HTTPURLResponse(url: request.url!, statusCode: reply.status, httpVersion: nil, headerFields: nil)!)
    }
}
@MainActor
private struct ObservationSession {
    let server: ObservationServer
    let client: SessionController
    let loop: FinancialLoopModel
    init(_ replies: [ObservationReply]) async throws {
        let server = ObservationServer(replies), storage = MemoryStore()
        let config = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!, supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let client = try SessionController(configuration: config, storage: storage, fetch: { try await server.send($0) })
        self.server = server; self.client = client
        let accounts = AccountsModel(controller: client)
        loop = FinancialLoopModel(controller: client, accounts: accounts, journal: FinancialWriteJournal(storage: storage, prefix: config.storagePrefix))
        let identity = try await client.login(email: "alice@example.test", password: "test", captchaToken: "test")
        accounts.bind(identity); loop.bind(identity)
    }
}

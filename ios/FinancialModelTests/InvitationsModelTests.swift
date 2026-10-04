import Foundation
import XCTest
import ArgusSession
@testable import InvitationModels

/// Answers `/api/v1/invites` in the server's shapes, in the order queued, and can hold one call open.
actor InvitesStub: InvitesTransport {
    struct Sent: Equatable, Sendable { let call: String; let key: String? }
    private var queued: [String: [Result<String, SessionFailure>]] = [:]
    private var holding: Set<String> = []
    private var held: [String: [CheckedContinuation<Void, Never>]] = [:]
    private(set) var sent: [Sent] = []

    func reply(_ call: String, _ json: String) { queued[call, default: []].append(.success(json)) }
    func fail(_ call: String, _ failure: SessionFailure) { queued[call, default: []].append(.failure(failure)) }
    func holdNext(_ call: String) { holding.insert(call) }
    func release(_ call: String) { held.removeValue(forKey: call)?.forEach { $0.resume() } }
    func isHolding(_ call: String) -> Bool { held[call]?.isEmpty == false }
    func calls() -> [String] { sent.map(\.call) }
    func keys(_ call: String) -> [String?] { sent.filter { $0.call == call }.map(\.key) }

    func send(route: String, path: String, method: String, body: Data?, key: String?) async throws -> Data {
        let call = method + " " + path
        sent.append(Sent(call: call, key: key))
        let reply = queued[call]?.isEmpty == false ? queued[call]!.removeFirst() : .failure(.unavailable)
        if holding.remove(call) != nil { await withCheckedContinuation { held[call, default: []].append($0) } }
        return Data(try reply.get().utf8)
    }
}

enum Wire {
    static let access = "GET /access", sent = "GET ", create = "POST ", redeem = "POST /redeem", preview = "POST /preview"
    static let links = "GET /group-links", createLink = "POST /group-links"
    static func access(admitted: Bool) -> String {
        #"{"gate_enabled":true,"admitted":\#(admitted),"waitlist_url":"https://cuadrao.ai","testflight_url":null}"#
    }
    static let admittedByRedeem = #"{"admitted":true,"outcome":"admitted","kind":"beta","replayed":false}"#
    static func preview(_ kind: String, available: Bool = true) -> String {
        #"{"kind":"\#(kind)","available":\#(available),"expires_at":"2026-10-10T18:30:00Z","household_name":null}"#
    }
    static func sent(remaining: Int) -> String { #"{"quota":{"limit":10,"used":\#(10 - remaining),"remaining":\#(remaining)},"invitations":[]}"# }
    static let id = "8d0f7a8e-5a35-4f43-9b7f-0d1f1b8f2a11"
    static func created(kind: String = "beta", secrets: Bool = true) -> String {
        let code = secrets ? #""7K2M-9QXD-4RTA""# : "null", token = secrets ? #""tok3n-value-from-server""# : "null"
        let group = kind == "group_link"
        return #"{"invitation":{"id":"\#(id)","kind":"\#(kind)","expires_at":"2026-10-10T18:30:00Z","token":\#(token),"code":\#(code),"link":null,"source_label":\#(group ? #""Cena""# : "null"),"cap":\#(group ? "25" : "null"),"replayed":\#(!secrets)},"quota":\#(group ? "null" : #"{"limit":10,"used":4,"remaining":6}"#)}"#
    }
    static func links(redeemed: Int = 0) -> String {
        #"{"links":[{"id":"\#(id)","source_label":"Cena","cap":25,"redeemed":\#(redeemed),"overflow":0,"expires_at":"2026-10-10T18:30:00Z","revoked_at":null,"state":"open"}]}"#
    }
    static let betaLink = URL(string: "https://cuadrao.ai/invite#beta-link-token-000000000000000000000000001")!
    static let token = "beta-link-token-000000000000000000000000001"
}

@MainActor
final class InvitationsModelTests: XCTestCase {
    private let stub = InvitesStub()
    private var destinations: InviteDestinations { InviteDestinations(waitlist: URL(string: "https://cuadrao.ai"), testFlight: nil) }

    private func model(surface: Bool = true, links: Bool = true, signedIn: Bool = true) -> InvitationsModel {
        let stub = self.stub
        let model = InvitationsModel(flags: InvitationFlags(surface: surface, links: links)) { _ in InvitesClient(transport: stub) }
        if signedIn { model.bind(identity(1)) }
        return model
    }
    private func identity(_ revision: UInt64) -> SessionSnapshot { SessionSnapshot(phase: .authenticated, profile: nil, revision: revision) }
    private func held(_ call: String) async {
        for _ in 0..<10_000 { if await stub.isHolding(call) { return }; await Task.yield() }
        XCTFail("\(call) was never sent")
    }

    // MARK: Admission

    func testAFirstCheckWithoutAnAnswerStaysClosedUntilARetryIsAnswered() async {
        let model = model()
        XCTAssertEqual(model.admission, .checking)
        await model.refreshAccess()
        XCTAssertEqual(model.admission, .unanswered)
        XCTAssertFalse(model.showsInvitations)
        await stub.fail(Wire.access, .unauthorized)
        await model.refreshAccess()
        XCTAssertEqual(model.admission, .unanswered)
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.retryAccess()
        XCTAssertEqual(model.admission, .required(destinations))
    }

    func testAFailedRefreshNeverReplacesTheServersAnswer() async {
        for admitted in [false, true] {
            let model = model()
            await stub.reply(Wire.access, Wire.access(admitted: admitted))
            await model.refreshAccess()
            let answer = model.admission
            XCTAssertEqual(answer, admitted ? .admitted(destinations) : .required(destinations))
            await stub.fail(Wire.access, .unavailable)
            await model.refreshAccess()
            await stub.fail(Wire.access, .unauthorized)
            await model.refreshAccess()
            XCTAssertEqual(model.admission, answer)
        }
    }

    func testTheServersSurfaceOffAnswerIsTodaysApp() async {
        let model = model()
        await stub.fail(Wire.access, .rejected(status: 404, code: "invites_unavailable"))
        await model.refreshAccess()
        XCTAssertEqual(model.admission, .off)
        XCTAssertFalse(model.showsInvitations)
    }

    func testTheClientFlagOffSendsNoRequestAndNeverWaits() async {
        let model = model(surface: false, signedIn: false)
        XCTAssertEqual(model.admission, .off)
        model.bind(identity(1))
        XCTAssertEqual(model.admission, .off)
        await model.refreshAccess()
        await model.retryAccess()
        XCTAssertEqual(model.admission, .off)
        XCTAssertFalse(model.showsInvitations)
        let calls = await stub.calls()
        XCTAssertEqual(calls, [])
    }

    func testAnOlderAccessReadCannotLandOverANewerOne() async {
        let model = model()
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await stub.reply(Wire.access, Wire.access(admitted: true))
        await stub.holdNext(Wire.access)
        let stale = Task { await model.refreshAccess() }
        await held(Wire.access)
        await model.refreshAccess()
        XCTAssertEqual(model.admission, .admitted(destinations))
        await stub.release(Wire.access)
        await stale.value
        XCTAssertEqual(model.admission, .admitted(destinations))
    }

    func testARedeemedCodeAdmitsEvenWhenAnOlderReadAndTheFollowUpReadDisagreeOrFail() async {
        let model = model()
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.refreshAccess()
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await stub.holdNext(Wire.access)
        let stale = Task { await model.refreshAccess() }
        await held(Wire.access)
        await stub.reply(Wire.redeem, Wire.admittedByRedeem)
        await stub.fail(Wire.access, .unavailable)
        await model.submitCode("BETA-0000-0001")
        XCTAssertEqual(model.admission, .admitted(destinations))
        await stub.release(Wire.access)
        await stale.value
        XCTAssertEqual(model.admission, .admitted(destinations))
        XCTAssertEqual(model.gate, .ready)
    }

    func testEachRedeemRefusalIsExplainedAndTheGateStaysClosed() async {
        let cases: [(SessionFailure, InvitationProblem)] = [
            (.rejected(status: 404, code: "invitation_not_found"), .invalid), (.rejected(status: 409, code: "invitation_expired"), .expired),
            (.rejected(status: 409, code: "invitation_consumed"), .used), (.rejected(status: 409, code: "invitation_revoked"), .revoked),
            (.rejected(status: 409, code: "group_link_full"), .full), (.rejected(status: 429, code: "invite_rate_limited"), .rateLimited),
            (.unavailable, .unavailable),
        ]
        let model = model()
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.refreshAccess()
        for (failure, problem) in cases {
            await stub.fail(Wire.redeem, failure)
            await model.submitCode("7K2M-9QXD-4RTA")
            XCTAssertEqual(model.gate, .problem(problem))
            XCTAssertEqual(model.admission, .required(destinations))
        }
    }

    // MARK: Links

    func testALinkAtTheGateFillsTheCodeAndRedeemsOnlyWhenThePersonSubmits() async {
        let model = model()
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.refreshAccess()
        let handled = await model.open(Wire.betaLink)
        XCTAssertTrue(handled)
        XCTAssertNil(model.pendingLink)
        XCTAssertEqual(model.gateCode, Wire.token)
        XCTAssertEqual(model.admission, .required(destinations))
        var calls = await stub.calls()
        XCTAssertEqual(calls, [Wire.access])
        await stub.fail(Wire.redeem, .rejected(status: 409, code: "invitation_expired"))
        await model.submitCode(model.gateCode)
        XCTAssertEqual(model.gate, .problem(.expired))
        for _ in 0..<3 {
            await stub.reply(Wire.access, Wire.access(admitted: false))
            await model.refreshAccess()
        }
        calls = await stub.calls()
        XCTAssertEqual(calls.filter { $0 == Wire.redeem }.count, 1)
        XCTAssertFalse(calls.contains(Wire.preview))
    }

    func testALinkWaitsForSignInAndForTheServersAnswer() async {
        let model = model(signedIn: false)
        _ = await model.open(Wire.betaLink)
        XCTAssertEqual(model.pendingLink, .token(Wire.token))
        model.bind(identity(1))
        XCTAssertEqual(model.pendingLink, .token(Wire.token))
        await model.refreshAccess()
        XCTAssertEqual(model.admission, .unanswered)
        XCTAssertEqual(model.pendingLink, .token(Wire.token))
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.retryAccess()
        XCTAssertNil(model.pendingLink)
        XCTAssertEqual(model.gateCode, Wire.token)
        let calls = await stub.calls()
        XCTAssertFalse(calls.contains(Wire.redeem))
    }

    func testALinkEndsWithTheSessionAndNeverReachesTheNextAccount() async {
        let model = model()
        await model.refreshAccess()
        _ = await model.open(Wire.betaLink)
        XCTAssertEqual(model.pendingLink, .token(Wire.token))
        model.bind(nil)
        XCTAssertNil(model.pendingLink)
        model.bind(identity(2))
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.refreshAccess()
        XCTAssertEqual(model.gateCode, "")
        let calls = await stub.calls()
        XCTAssertEqual(calls, [Wire.access, Wire.access])
    }

    func testADiscardedLinkIsGone() async {
        let model = model(signedIn: false)
        _ = await model.open(Wire.betaLink)
        model.discardPendingLink()
        model.bind(identity(1))
        await stub.reply(Wire.access, Wire.access(admitted: false))
        await model.refreshAccess()
        XCTAssertEqual(model.gateCode, "")
    }

    func testWithTheLinkFlagOffNoLinkOfAnySchemeIsHandled() async {
        var opened: [String] = []
        for surface in [true, false] {
            let model = model(surface: surface, links: false)
            model.openHousehold = { opened.append($0); return true }
            await stub.reply(Wire.access, Wire.access(admitted: false))
            await model.refreshAccess()
            for link in ["https://cuadrao.ai/invite#beta-link-token-0000000000000000000000001", "argus-household://invite#household-link-token-00000000000000"] {
                let handled = await model.open(URL(string: link)!)
                XCTAssertFalse(handled, link)
                XCTAssertNil(model.pendingLink, link)
                XCTAssertEqual(model.gateCode, "", link)
            }
        }
        let calls = await stub.calls()
        XCTAssertEqual(calls, [Wire.access])
        XCTAssertEqual(opened, [])
    }

    func testAnAdmittedPersonsLinkIsPreviewedOnceAndNeverRedeemed() async {
        var opened: [String] = []
        let model = model()
        model.openHousehold = { opened.append($0); return true }
        await stub.reply(Wire.access, Wire.access(admitted: true))
        await model.refreshAccess()
        await stub.reply(Wire.preview, Wire.preview("beta", available: false))
        _ = await model.open(Wire.betaLink)
        XCTAssertEqual(model.notice, .alreadyAdmitted)
        await stub.reply(Wire.preview, Wire.preview("household"))
        _ = await model.open(URL(string: "argus-household://invite#household-link-token-00000000000000")!)
        XCTAssertEqual(opened, ["household-link-token-00000000000000"])
        await stub.fail(Wire.preview, .rejected(status: 404, code: "invitation_not_found"))
        _ = await model.open(Wire.betaLink)
        XCTAssertEqual(model.notice, .problem(.invalid))
        await stub.reply(Wire.access, Wire.access(admitted: true))
        await model.refreshAccess()
        let calls = await stub.calls()
        XCTAssertEqual(calls, [Wire.access, Wire.preview, Wire.preview, Wire.preview, Wire.access])
        XCTAssertEqual(model.admission, .admitted(destinations))
    }

    func testASecondLinkOpenedWhileTheFirstIsBeingPreviewedIsNotDropped() async {
        var opened: [String] = []
        let model = model()
        model.openHousehold = { opened.append($0); return true }
        await stub.reply(Wire.access, Wire.access(admitted: true))
        await model.refreshAccess()
        await stub.reply(Wire.preview, Wire.preview("household"))
        await stub.reply(Wire.preview, Wire.preview("household"))
        await stub.holdNext(Wire.preview)
        let first = Task { await model.open(URL(string: "argus-household://invite#first-household-token-0000000000000")!) }
        await held(Wire.preview)
        _ = await model.open(URL(string: "argus-household://invite#second-household-token-000000000000")!)
        await stub.release(Wire.preview)
        _ = await first.value
        XCTAssertEqual(Set(opened), ["first-household-token-0000000000000", "second-household-token-000000000000"])
    }

    func testWithTheSurfaceOffALinkOnlyOpensTheHouseholdJoinStep() async {
        var opened: [String] = []
        let model = model(surface: false)
        model.openHousehold = { opened.append($0); return true }
        _ = await model.open(Wire.betaLink)
        XCTAssertEqual(opened, [Wire.token])
        let calls = await stub.calls()
        XCTAssertEqual(calls, [])
    }

    // MARK: Sending

    func testAPersonalCreateWithoutAnAnswerAsksAgainWithTheSameKeyAndADefiniteRefusalRetiresIt() async {
        let model = model()
        await stub.reply(Wire.sent, Wire.sent(remaining: 7))
        await model.loadPersonal()
        await model.createPersonal()
        XCTAssertEqual(model.notice, .problem(.unavailable))
        XCTAssertEqual(model.personal.value?.quota.remaining, 7)
        await stub.fail(Wire.create, .rejected(status: 409, code: "idempotency_conflict"))
        await model.createPersonal()
        await stub.reply(Wire.create, Wire.created())
        await model.createPersonal()
        let keys = await stub.keys(Wire.create)
        XCTAssertEqual(keys.count, 3)
        XCTAssertEqual(keys[0], keys[1])
        XCTAssertNotEqual(keys[1], keys[2])
        XCTAssertEqual(model.createdPersonal?.code, "7K2M-9QXD-4RTA")
        XCTAssertNil(model.createdPersonal?.link)
        XCTAssertEqual(model.personal.value?.quota.remaining, 6)
        XCTAssertFalse(model.creatingPersonal)
    }

    func testAnEmptySentListALoadingOneAndAFailedOneAreDifferent() async {
        let model = model()
        XCTAssertEqual(model.personal, .loading)
        await model.loadPersonal()
        XCTAssertEqual(model.personal, .failed)
        await stub.reply(Wire.sent, Wire.sent(remaining: 10))
        await model.loadPersonal()
        XCTAssertEqual(model.personal.value?.invitations, [])
        await model.loadPersonal()
        XCTAssertEqual(model.personal.value?.quota.remaining, 10)
    }

    func testFounderStatusComesOnlyFromTheServersRefusal() async {
        let model = model()
        XCTAssertEqual(model.groupLinks, .loading)
        await model.loadGroupLinks()
        XCTAssertEqual(model.groupLinks, .failed)
        await stub.fail(Wire.links, .rejected(status: 403, code: "founder_required"))
        await model.loadGroupLinks()
        XCTAssertEqual(model.groupLinks, .ready(.notFounder))
    }

    func testANewGroupLinksSecretsSurviveAFailedListReload() async throws {
        let model = model()
        await stub.reply(Wire.links, #"{"links":[]}"#)
        await model.loadGroupLinks()
        await stub.reply(Wire.createLink, Wire.created(kind: "group_link"))
        await model.createGroupLink(label: "Cena", cap: 25, expiresAt: Date().addingTimeInterval(86_400))
        guard case .created(let invite, used: 0) = model.group else { return XCTFail("\(model.group)") }
        XCTAssertEqual(invite.code, "7K2M-9QXD-4RTA")
        XCTAssertEqual(model.groupLinks, .ready(.links([])))
        await stub.reply(Wire.links, Wire.links(redeemed: 3))
        await model.loadGroupLinks()
        guard case .created(_, used: 3) = model.group else { return XCTFail("\(model.group)") }
    }

    func testAGroupLinkKeyBelongsToOneDraft() async {
        let model = model()
        let expiry = Date().addingTimeInterval(86_400)
        await model.createGroupLink(label: "Cena", cap: 25, expiresAt: expiry)
        await model.createGroupLink(label: "Cena", cap: 25, expiresAt: expiry)
        await model.createGroupLink(label: "Cena", cap: 30, expiresAt: expiry)
        let keys = await stub.keys(Wire.createLink)
        XCTAssertEqual(keys.count, 3)
        XCTAssertEqual(keys[0], keys[1])
        XCTAssertNotEqual(keys[1], keys[2])
        XCTAssertEqual(model.group, .draft)
    }

    func testAGroupLinkOutsideTheServersLimitsIsExplainedWithoutARequest() async {
        let model = model()
        let week = Date().addingTimeInterval(7 * 86_400)
        await model.createGroupLink(label: "Cena", cap: 20_000, expiresAt: week)
        XCTAssertEqual(model.notice, .groupLink(.cap))
        await model.createGroupLink(label: String(repeating: "a", count: 81), cap: 5, expiresAt: week)
        XCTAssertEqual(model.notice, .groupLink(.label))
        await model.createGroupLink(label: "Cena", cap: 5, expiresAt: Date().addingTimeInterval(400 * 86_400))
        XCTAssertEqual(model.notice, .groupLink(.expiry))
        let calls = await stub.calls()
        XCTAssertEqual(calls, [])
        await stub.fail(Wire.createLink, .rejected(status: 422, code: "invite_request_invalid"))
        await model.createGroupLink(label: "Cena", cap: 5, expiresAt: week)
        XCTAssertEqual(model.notice, .problem(.refused))
    }
}

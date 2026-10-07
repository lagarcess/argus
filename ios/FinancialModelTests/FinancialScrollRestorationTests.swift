import Foundation
import XCTest
@testable import ArgusSession
@testable import FinancialModels

@MainActor
final class FinancialScrollRestorationTests: XCTestCase {
    func testPlanRoutesRoundTripOffsetsAndDecodeLegacyAnchors() throws {
        let record = UUID(), activity = UUID()
        try assertPositionCoding(FinancialBudgetNavigation(budgetID: record, origin: .plan,
            activityID: activity, anchor: activity), offset: \.anchorOffset)
        try assertPositionCoding(FinancialGoalNavigation(goalID: record, origin: .home,
            activityID: activity, anchor: activity, occurrenceID: "scheduled-contribution"), offset: \.anchorOffset)
        try assertPositionCoding(FinancialDebtNavigation(debtID: record, origin: .searchAccount,
            activityID: activity, anchor: activity, occurrenceID: "scheduled-payment"), offset: \.anchorOffset)
    }

    func testInitialFramesWaitForLoadedRowsBeforeRestoration() {
        let anchor = UUID().uuidString
        var phase = FinancialScrollRestorationPhase.waitingForContent
        phase.prepare(anchor: anchor, offset: -23.5, availableAnchors: nil)
        XCTAssertEqual(phase, .waitingForContent)
        phase.prepare(anchor: anchor, offset: -23.5, availableAnchors: [anchor])
        guard case .restoring(let restoration) = phase else { return XCTFail("Saved position must restore before recording initial frames") }
        XCTAssertEqual(restoration.anchor, anchor)
        XCTAssertEqual(restoration.offset, -23.5)
        XCTAssertEqual(restoration.adjustment(rowOffset: 276.5, contentOffset: 0, minimum: 0, maximum: 1200), .move(300))
        phase.restored(UUID())
        XCTAssertEqual(phase, .restoring(restoration), "A retired layout callback cannot complete another restoration")
        phase.restored(restoration.id)
        XCTAssertEqual(phase, .tracking)
    }

    func testRetainedPageDoesNotRestoreAgainAfterActivityBackOrRefresh() {
        let anchor = UUID().uuidString
        var phase = FinancialScrollRestorationPhase.waitingForContent
        phase.prepare(anchor: nil, offset: nil, availableAnchors: [anchor])
        XCTAssertEqual(phase, .tracking)
        phase.prepare(anchor: anchor, offset: 178.25, availableAnchors: nil)
        phase.prepare(anchor: anchor, offset: 178.25, availableAnchors: [anchor, UUID().uuidString])
        XCTAssertEqual(phase, .tracking, "A loaded page keeps its natural native scroll position")
    }

    func testMissingAnchorAndUserDragDoNotLeaveRestorationPending() {
        let anchor = UUID().uuidString
        var phase = FinancialScrollRestorationPhase.waitingForContent
        phase.prepare(anchor: anchor, offset: -23.5, availableAnchors: [])
        XCTAssertEqual(phase, .tracking)
        phase = .waitingForContent
        phase.prepare(anchor: anchor, offset: nil, availableAnchors: [anchor])
        guard case .restoring(let legacy) = phase else { return XCTFail("A legacy anchor remains restorable") }
        XCTAssertEqual(legacy.offset, 0)
        phase.prepare(anchor: anchor, offset: nil, availableAnchors: [])
        XCTAssertEqual(phase, .tracking, "Removing a row also retires an in-flight restoration")
        phase = .restoring(legacy)
        phase.userScrolled()
        phase.prepare(anchor: anchor, offset: nil, availableAnchors: [anchor])
        XCTAssertEqual(phase, .tracking, "A person's drag cancels the pending automatic movement")
    }

    func testPlanModelsPreserveViewportThroughNativeActivityAndRelaunch() throws {
        let storage = MemoryStore()
        let configuration = try SessionConfiguration(argusAPIURL: URL(string: "https://api.example.test")!,
            supabaseURL: URL(string: "https://auth.example.test")!, publicAnonKey: "sb_publishable_test", keychainService: UUID().uuidString)
        let controller = try SessionController(configuration: configuration, storage: storage, fetch: { _ in throw SessionFailure.unavailable })
        let accounts = AccountsModel(controller: controller)
        let loop = FinancialLoopModel(controller: controller, accounts: accounts,
            journal: FinancialWriteJournal(storage: storage, prefix: configuration.storagePrefix))
        let name = UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: name))
        defer { defaults.removePersistentDomain(forName: name) }
        let budget = FinancialBudgetModel(controller: controller, loop: loop, defaults: defaults)
        let goal = FinancialGoalModel(controller: controller, loop: loop, defaults: defaults)
        let debt = FinancialDebtModel(controller: controller, loop: loop, defaults: defaults)
        let owner = UUID().uuidString
        let identity = SessionSnapshot(phase: .authenticated,
            profile: SessionProfile(id: owner, email: nil, displayName: nil, language: "en"), revision: 1)
        let record = UUID(), anchor = UUID(), activity = UUID()
        let savedOffset = -23.5
        let encoder = JSONEncoder()
        let cases: [(kind: String, saved: Data, bind: @MainActor (SessionSnapshot?) -> Void,
                     context: @MainActor () -> FinancialScrollContext?, activity: @MainActor (UUID?, Bool) -> Void)] = [
            ("budget", try encoder.encode(FinancialBudgetNavigation(budgetID: record, origin: .plan, anchor: anchor, anchorOffset: savedOffset)),
             budget.bind, { budget.scrollContext }, budget.activity),
            ("goal", try encoder.encode(FinancialGoalNavigation(goalID: record, origin: .home, anchor: anchor, anchorOffset: savedOffset)),
             goal.bind, { goal.scrollContext }, goal.activity),
            ("debt", try encoder.encode(FinancialDebtNavigation(debtID: record, origin: .searchAccount, anchor: anchor, anchorOffset: savedOffset)),
             debt.bind, { debt.scrollContext }, debt.activity),
        ]
        for model in cases {
            let key = "financial." + model.kind + ".navigation." + owner
            defaults.set(model.saved, forKey: key)
            model.bind(identity)
            let original = try XCTUnwrap(model.context())
            XCTAssertNil(original.availableAnchors, "Initial unloaded detail cannot replace the saved position")
            original.remember(activity.uuidString, 300)
            XCTAssertEqual(model.context()?.anchor, anchor.uuidString)
            XCTAssertEqual(model.context()?.offset, savedOffset)
            model.activity(activity, true)
            XCTAssertFalse(try XCTUnwrap(model.context()).active)
            XCTAssertEqual(model.context()?.anchor, anchor.uuidString, "Opening a row must not replace the visible row anchor")
            model.bind(identity)
            let reopened = try XCTUnwrap(model.context())
            XCTAssertNotEqual(reopened.id, original.id, "A new session binding starts a fresh page restoration")
            XCTAssertFalse(reopened.active, "A nested activity remains the selected destination after relaunch")
            XCTAssertEqual(reopened.offset, savedOffset)
            model.activity(nil, true)
            XCTAssertTrue(try XCTUnwrap(model.context()).active)
            XCTAssertEqual(model.context()?.offset, savedOffset)
            model.activity(activity, false)
            XCTAssertEqual(model.context()?.anchor, activity.uuidString, "Foundation retains its legacy tapped-row anchor")
            XCTAssertNil(model.context()?.offset)
            model.bind(nil)
            original.remember(anchor.uuidString, 0)
            XCTAssertNil(model.context())
            XCTAssertNil(defaults.data(forKey: key), "Sign-out removes the owner-scoped route")
        }
    }

    private func assertPositionCoding<Route: Codable & Equatable>(_ route: Route,
        offset: WritableKeyPath<Route, Double?>, file: StaticString = #filePath, line: UInt = #line) throws {
        var positioned = route
        positioned[keyPath: offset] = -23.5
        let data = try JSONEncoder().encode(positioned)
        XCTAssertEqual(try JSONDecoder().decode(Route.self, from: data), positioned, file: file, line: line)
        var legacy = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        legacy.removeValue(forKey: "anchorOffset")
        let restored = try JSONDecoder().decode(Route.self, from: JSONSerialization.data(withJSONObject: legacy))
        let legacyMatches = restored == route
        XCTAssertTrue(legacyMatches, "Missing offset must not discard the existing route", file: file, line: line)
    }
}

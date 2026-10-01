import Foundation
import XCTest
@testable import ArgusSession

final class HouseholdPlanTests: XCTestCase {
    func testFourKindsDecodeOnlyTheirDisclosedProgressAndCapabilities() throws {
        for kind in HouseholdPlanKind.allCases {
            var wire = SharedPlanTestData.plan(kind)
            wire["permission"] = "view"; wire["is_owner"] = false
            let contribution = SharedPlanTestData.contribution(canCorrect: true)
            wire["contributions"] = [contribution]
            let plan = try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire))
            XCTAssertEqual(plan.ref.kind, kind)
            XCTAssertFalse(plan.canEdit)
            XCTAssertFalse(plan.canManagePeople)
            XCTAssertTrue(plan.canContribute)
            XCTAssertTrue(plan.contributions[0].canCorrect)
            XCTAssertNil(plan.contributions[0].original)
            if case .goal(let c, let planned, let projected) = plan.progress {
                XCTAssertNil(c.actualMinor); XCTAssertEqual(planned, "12000"); XCTAssertNil(projected)
            }
            if case .budget(_, _, _, let spent, let over) = plan.progress { XCTAssertEqual(spent, "1700"); XCTAssertFalse(over) }
        }
    }
    func testUnknownKindAndMissingKindSpecificValuesFailClosed() throws {
        var wire = SharedPlanTestData.plan(.budget)
        wire["ref"] = ["id": SharedPlanTestData.planId.uuidString, "kind": "unsupported"]
        XCTAssertThrowsError(try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire)))
        wire = SharedPlanTestData.plan(.budget)
        wire["progress"] = ["actual_minor": NSNull(), "applied_minor": NSNull(), "remaining_minor": NSNull(), "state": "unknown"]
        XCTAssertThrowsError(try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire)))
    }
    func testDepartureHistoryHasNoEditContributionOrRestoreCapability() throws {
        var wire = SharedPlanTestData.plan(.goal)
        wire["archived"] = true; wire["read_only"] = true; wire["archive_reason"] = "owner_departed"
        let plan = try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire))
        XCTAssertEqual(plan.archiveReason, "owner_departed")
        XCTAssertFalse(plan.canEdit); XCTAssertFalse(plan.canManagePeople); XCTAssertFalse(plan.canContribute)
        XCTAssertFalse(plan.canRestore)
    }
    func testSearchPlanHasNoInventedAccountDestination() throws {
        let raw: [String: Any] = ["id": UUID().uuidString, "kind": "goal", "title": "Shared intention", "account_id": NSNull(), "activity_id": NSNull()]
        let hit = try JSONDecoder().decode(HouseholdSearchHit.self, from: JSONSerialization.data(withJSONObject: raw))
        XCTAssertNil(hit.accountId); XCTAssertNil(hit.activityId)
    }
    func testRestoreCapabilityIsExplicitEvenWhenArchiveIsReadOnly() throws {
        var wire = SharedPlanTestData.plan(.budget)
        wire["archived"] = true; wire["read_only"] = true; wire["can_restore"] = true
        let plan = try JSONDecoder().decode(HouseholdPlan.self, from: JSONSerialization.data(withJSONObject: wire))
        XCTAssertTrue(plan.canRestore); XCTAssertFalse(plan.canEdit); XCTAssertFalse(plan.canContribute)
    }
    func testJournalRestoresEveryTypedPlanOperationWithoutChangingBytes() throws {
        let actor = UUID(); let identity = SessionSnapshot(phase: .authenticated, profile: .init(id: actor.uuidString, email: nil, displayName: nil, language: nil), revision: 1)
        let store = MemoryStore(); let journal = FinancialWriteJournal(storage: store, prefix: UUID().uuidString)
        let ref = HouseholdPlanRef(kind: .goal, id: UUID())
        let actions: [HouseholdPlanAction] = [.create(.goal), .share(ref), .edit(ref), .people(ref), .record(ref), .link(ref), .correct(ref, claim: UUID()), .release(ref, claim: UUID()), .allocation(ref)]
        for action in actions {
            let write = PendingFinancialConfirmation(ownerId: actor, originAccountId: nil, route: "households", path: "/" + SharedPlanTestData.householdId.uuidString + "/plan" + action.path, method: action.method, body: Data(#"{ "membership_id": "exact", "activity": { "preview_token": "reviewed" } }"#.utf8), key: UUID(), householdMembershipId: SharedPlanTestData.memberId, householdAuthorizationVersion: 7, householdOperation: .plan(householdId: SharedPlanTestData.householdId, action: action))
            try journal.begin(write, for: identity)
            XCTAssertEqual(try journal.pending(for: identity), write)
            XCTAssertEqual(try journal.pending(for: identity)?.householdOperation, write.householdOperation)
            try journal.clear(write, for: identity)
        }
    }
    func testExplicitDateClearDiffersFromUnchangedDate() throws {
        let clear = try JSONEncoder().encode(HouseholdPlanDefinitionPatch(includesTargetDate: true))
        let unchanged = try JSONEncoder().encode(HouseholdPlanDefinitionPatch(name: "New title"))
        XCTAssertTrue((try JSONSerialization.jsonObject(with: clear) as! [String: Any])["target_date"] is NSNull)
        XCTAssertNil((try JSONSerialization.jsonObject(with: unchanged) as! [String: Any])["target_date"])
    }
    func testLegacyHouseholdActivityJournalPreservesExactRecoveryEnvelope() throws {
        let actor = UUID(), household = UUID(), activity = UUID(), membership = UUID(), key = UUID()
        let body = Data(#"{ "activity": { "amount": "18.25", "preview_token": "reviewed" } }"#.utf8)
        for (path, method, operation) in [
            ("/" + household.uuidString + "/activities", "POST", HouseholdWriteOperation.activity(householdId: household, activityId: nil)),
            ("/" + household.uuidString + "/activities/" + activity.uuidString, "PATCH", HouseholdWriteOperation.activity(householdId: household, activityId: activity)),
            ("/" + household.uuidString + "//activities", "POST", .management),
            ("/" + household.uuidString + "/activities/archive", "POST", .management)
        ] {
            let raw: [String: Any] = ["ownerId": actor.uuidString, "route": "households", "path": path, "method": method, "body": body.base64EncodedString(), "key": key.uuidString, "householdMembershipId": membership.uuidString, "householdAuthorizationVersion": 9]
            let write = try JSONDecoder().decode(PendingFinancialConfirmation.self, from: JSONSerialization.data(withJSONObject: raw))
            XCTAssertEqual(write.householdOperation, operation); XCTAssertEqual(write.ownerId, actor)
            XCTAssertEqual(write.body, body); XCTAssertEqual(write.key, key); XCTAssertEqual(write.householdMembershipId, membership); XCTAssertEqual(write.householdAuthorizationVersion, 9)
        }
    }
    func testResponsibilityContainsExactlyItsChosenScopeAndOptionalUnequalAmount() throws {
        let writes = [HouseholdPlanResponsibilityWrite(membershipId: UUID(), amount: "37.25", period: .month("2026-10")), HouseholdPlanResponsibilityWrite(membershipId: UUID(), amount: nil, period: .occurrence(UUID()))]
        let items = try JSONSerialization.jsonObject(with: JSONEncoder().encode(writes)) as! [[String: Any]]
        XCTAssertEqual(items[0]["amount"] as? String, "37.25"); XCTAssertEqual(items[0]["period"] as? String, "2026-10")
        XCTAssertTrue(items[1]["amount"] is NSNull); XCTAssertNotNil(items[1]["occurrence_id"]); XCTAssertNil(items[1]["period"])
    }
}

enum SharedPlanTestData {
    static let householdId = UUID(), memberId = UUID(), planId = UUID(), claimId = UUID()
    static func contribution(canCorrect: Bool = false) -> [String: Any] {
        ["id": claimId.uuidString, "person": person(), "amount_minor": "1700", "applied_minor": "1700", "currency": "DOP", "currency_fraction_digits": 2, "date": "2026-10-01", "status": "current", "original": NSNull(), "purpose": "spending", "occurrence_id": NSNull(), "can_correct": canCorrect, "can_release": canCorrect]
    }
    static func person() -> [String: Any] { ["membership_id": memberId.uuidString, "display_name": "Synthetic member"] }
    static func plan(_ kind: HouseholdPlanKind, version: Int = 1) -> [String: Any] {
        let schedule: [String: Any] = ["cadence": "monthly", "start_date": "2026-10-01", "end_date": NSNull(), "month_days": [1]]
        var definition: [String: Any] = ["name": "Synthetic " + kind.rawValue, "currency": "DOP", "currency_fraction_digits": 2]
        var progress: [String: Any] = ["actual_minor": NSNull(), "applied_minor": "1700", "remaining_minor": NSNull(), "state": "unknown", "debt_balance_minor": NSNull(), "debt_state": NSNull()]
        switch kind {
        case .budget: definition.merge(["limit_minor": "10000", "month": "2026-10", "category_ids": ["groceries"], "include_uncategorized": false, "publish_budget_scope": true]) { _, n in n }; progress.merge(["gross_minor": "1900", "refunds_minor": "200", "spent_minor": "1700", "over_budget": false]) { _, n in n }
        case .bill, .debt: definition.merge(["amount_minor": "10000", "schedule": schedule]) { _, n in n }
        case .goal: definition.merge(["target_minor": "100000", "target_date": NSNull(), "schedule": schedule, "planned_contribution_minor": "1000"]) { _, n in n }; progress.merge(["planned_minor": "12000", "projected_minor": NSNull()]) { _, n in n }
        }
        var value: [String: Any] = ["ref": ["kind": kind.rawValue, "id": planId.uuidString], "version": version, "household_id": householdId.uuidString, "membership_id": memberId.uuidString, "authorization_version": 1, "owner": person(), "permission": "edit", "is_owner": true, "participants": [], "responsibilities": [], "occurrences": [], "contributions": [], "progress": progress, "archived": false, "read_only": false, "can_restore": false, "archive_reason": NSNull(), "definition": definition]
        if kind == .goal { value["allocations"] = [] }
        return value
    }
}

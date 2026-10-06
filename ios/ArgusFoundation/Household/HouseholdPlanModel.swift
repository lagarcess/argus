import SwiftUI
import Combine
import ArgusSession

@MainActor
final class HouseholdPlanModel: ObservableObject {
    enum State { case idle, loading, ready, unavailable, disabled }
    enum Origin: String { case home, plan, search }
    enum Sheet: Identifiable {
        case create, share, edit(HouseholdPlan), people(HouseholdPlan), record(HouseholdPlan, HouseholdPlanContribution?), link(HouseholdPlan), allocation(HouseholdPlan), original(HouseholdPlan, HouseholdPlanContribution)
        var id: String {
            switch self { case .create: "create"; case .share: "share"; case .edit(let p): "edit-" + p.id.uuidString; case .people(let p): "people-" + p.id.uuidString; case .record(let p, let c): "record-" + p.id.uuidString + (c?.id.uuidString ?? ""); case .link(let p): "link-" + p.id.uuidString; case .allocation(let p): "allocation-" + p.id.uuidString; case .original(_, let c): "original-" + c.id.uuidString }
        }
    }
    @Published private(set) var state = State.idle
    @Published private(set) var plans: [HouseholdPlan] = []
    @Published private(set) var detail: HouseholdPlan?
    @Published private(set) var detailLoading = false
    @Published private(set) var detailMissing = false
    @Published private(set) var history: [HouseholdPlan] = []
    @Published private(set) var errorKey: String?
    @Published var sheet: Sheet?
    @Published private(set) var origin = Origin.plan
    private(set) var openedRef: HouseholdPlanRef?
    private var generation = UUID()
    private var detailRequest = UUID()
    private weak var household: HouseholdModel?
    private var householdObservation: AnyCancellable?

    init(household: HouseholdModel) {
        self.household = household
        householdObservation = household.objectWillChange.sink { [weak self] _ in
            Task { @MainActor in self?.objectWillChange.send() }
        }
    }
    var pending: Bool { household?.pending != nil }
    var busy: Bool { household?.busy == true }
    var canStart: Bool { state == .ready && !pending && !busy }
    var controller: SessionController? { household?.controller }
    var identity: SessionSnapshot? { household?.identity }
    var scope: HouseholdPlanScope? {
        guard let h = household?.household, household?.active == true else { return nil }
        return .init(membershipId: h.membershipId, authorizationVersion: h.version)
    }
    func scope(_ plan: HouseholdPlan) -> HouseholdPlanScope { .init(membershipId: plan.membershipId, authorizationVersion: plan.authorizationVersion, planVersion: plan.version) }
    func clear() {
        generation = UUID(); detailRequest = UUID(); plans = []; detail = nil; openedRef = nil; history = []; sheet = nil; errorKey = nil; state = .idle; detailLoading = false; detailMissing = false
    }
    private func current(_ ticket: UUID, _ identity: SessionSnapshot, _ id: UUID, _ membership: UUID, _ version: Int) -> Bool {
        generation == ticket && household?.active == true && household?.selectedId == id && household?.identity?.revision == identity.revision && household?.identity?.profile?.id == identity.profile?.id && household?.household?.membershipId == membership && household?.household?.version == version
    }
    func isCurrent(_ plan: HouseholdPlan, _ identity: SessionSnapshot) -> Bool {
        household?.active == true && household?.selectedId == plan.householdId && household?.identity?.revision == identity.revision && household?.identity?.profile?.id == identity.profile?.id && household?.household?.membershipId == plan.membershipId && household?.household?.version == plan.authorizationVersion
    }
    func refresh() async {
        guard let household, household.active, let h = household.household, let identity else { return }
        let ticket = generation; state = .loading; errorKey = nil
        do {
            let value = try await household.controller.householdPlanResponse(HouseholdPlanSnapshot.self, householdId: h.id, expectedIdentity: identity)
            guard current(ticket, identity, h.id, h.membershipId, h.version) else { return }
            guard value.householdId == h.id, value.membershipId == h.membershipId, value.authorizationVersion == h.version,
                  value.plans.allSatisfy({ $0.householdId == h.id && $0.membershipId == h.membershipId && $0.authorizationVersion == h.version }) else { throw SessionFailure.invalidResponse }
            plans = value.plans; state = .ready
            if let ref = openedRef { await open(ref, origin: origin) }
        } catch {
            guard current(ticket, identity, h.id, h.membershipId, h.version) else { return }
            plans = []; detail = nil; sheet = nil; state = .unavailable; await failed(error, householdId: h.id)
        }
    }
    func options() async throws -> HouseholdPlanOptions {
        guard let household, household.active, let h = household.household, let identity else { throw SessionFailure.staleOperation }
        let ticket = generation
        do {
            let value = try await household.controller.householdPlanResponse(HouseholdPlanOptions.self, householdId: h.id, path: "/options", expectedIdentity: identity)
            guard current(ticket, identity, h.id, h.membershipId, h.version), value.membershipId == h.membershipId, value.authorizationVersion == h.version else { throw SessionFailure.staleOperation }
            return value
        } catch { if current(ticket, identity, h.id, h.membershipId, h.version) { await failed(error, householdId: h.id) }; throw error }
    }
    func open(_ ref: HouseholdPlanRef, origin: Origin) async {
        guard let household, household.active, let h = household.household, let identity else { return }
        let ticket = generation; let request = UUID(); detailRequest = request
        openedRef = ref; self.origin = origin; detail = nil; history = []; detailMissing = false; detailLoading = true; errorKey = nil
        defer { if detailRequest == request { detailLoading = false } }
        do {
            let value = try await household.controller.householdPlanResponse(HouseholdPlan.self, householdId: h.id, path: ref.path, expectedIdentity: identity)
            guard current(ticket, identity, h.id, h.membershipId, h.version), detailRequest == request else { return }
            guard value.ref == ref, value.householdId == h.id, value.membershipId == h.membershipId, value.authorizationVersion == h.version else { throw SessionFailure.invalidResponse }
            detail = value
        } catch {
            guard current(ticket, identity, h.id, h.membershipId, h.version), detailRequest == request else { return }
            if case SessionFailure.rejected(404, let code) = error, code != "household_not_found" && code != "household_access_unavailable" { detailMissing = true; errorKey = "sharedPlan.deleted" }
            else { await failed(error, householdId: h.id) }
        }
    }
    func back() { detailRequest = UUID(); detail = nil; openedRef = nil; history = []; errorKey = nil; detailMissing = false; detailLoading = false }
    func loadHistory(_ plan: HouseholdPlan) async {
        guard let household, let identity, isCurrent(plan, identity) else { return }
        let ticket = generation
        do {
            let value = try await household.controller.householdPlanResponse(HouseholdPlanHistory.self, householdId: plan.householdId, path: plan.ref.path + "/history", expectedIdentity: identity)
            guard generation == ticket, isCurrent(plan, identity), openedRef == plan.ref else { return }; history = value.items
        } catch { if generation == ticket, isCurrent(plan, identity) { await failed(error, householdId: plan.householdId) } }
    }
    func candidates(_ plan: HouseholdPlan) async throws -> [FinancialActivityDetail] {
        guard let household, let identity, isCurrent(plan, identity), plan.canContribute else { throw SessionFailure.staleOperation }
        let ticket = generation
        do {
            let result = try await household.controller.householdPlanResponse(HouseholdContributionCandidates.self, householdId: plan.householdId, path: plan.ref.path + "/contributions/candidates", expectedIdentity: identity)
            guard generation == ticket, isCurrent(plan, identity) else { throw SessionFailure.staleOperation }; return result.items
        } catch { if generation == ticket, isCurrent(plan, identity) { await failed(error, householdId: plan.householdId) }; throw error }
    }
    func review<Command: Encodable>(_ command: Command, plan: HouseholdPlan, claim: UUID? = nil) async throws -> HouseholdContributionPreview {
        guard let household, let identity, isCurrent(plan, identity), plan.canContribute else { throw SessionFailure.staleOperation }
        let ticket = generation
        let suffix = claim.map { "/contributions/" + $0.uuidString + "/preview" } ?? "/contributions/preview"
        do {
            let result = try await household.controller.householdPlanResponse(HouseholdContributionPreview.self, householdId: plan.householdId, path: plan.ref.path + suffix, method: "POST", body: JSONEncoder().encode(command), expectedIdentity: identity)
            guard generation == ticket, isCurrent(plan, identity), result.plan.ref == plan.ref, result.plan.membershipId == plan.membershipId, result.plan.authorizationVersion == plan.authorizationVersion else { throw SessionFailure.staleOperation }; return result
        } catch { if generation == ticket, isCurrent(plan, identity) { await failed(error, householdId: plan.householdId) }; throw error }
    }
    func submit<Command: Encodable>(_ command: Command, action: HouseholdPlanAction) async {
        guard let household, let scope, !pending, !busy else { return }
        do { try await household.confirmPlan(body: JSONEncoder().encode(command), scope: scope, action: action) }
        catch { errorKey = "household.storageError" }
    }
    func archive(_ plan: HouseholdPlan) async {
        guard plan.archived ? plan.canRestore : plan.canEdit else { return }
        await submit(HouseholdPlanEditCommand(scope: scope(plan), definition: .init(archived: !plan.archived)), action: .edit(plan.ref))
    }
    func release(_ contribution: HouseholdPlanContribution, plan: HouseholdPlan) async {
        guard plan.canContribute, contribution.canRelease else { return }
        await submit(scope(plan), action: .release(plan.ref, claim: contribution.id))
    }
    func show(_ next: Sheet) {
        guard canStart else { return }
        switch next {
        case .edit(let p): guard p.canEdit else { return }
        case .people(let p): guard p.canManagePeople || p.canEdit else { return }
        case .record(let p, let c): guard p.canContribute, c == nil || c?.canCorrect == true else { return }
        case .link(let p): guard p.canContribute else { return }
        case .allocation(let p): guard p.ref.kind == .goal, p.canContribute else { return }
        default: break
        }
        errorKey = nil; sheet = next
    }
    func openOriginal(_ contribution: HouseholdPlanContribution) async {
        guard contribution.original != nil, let plan = detail, let identity, isCurrent(plan, identity) else { return }
        sheet = .original(plan, contribution)
    }
    func writeResolved(_ receipt: HouseholdPlanReceipt) {
        sheet = nil
        if openedRef == receipt.plan.ref { detail = receipt.plan }
    }
    private func failed(_ error: Error, householdId: UUID) async {
        guard let household else { return }
        let ticket = generation
        if await household.handlePlanAccessFailure(error, householdId: householdId) {
            if !household.active { clear() }
            else if generation == ticket { detail = nil; sheet = nil; errorKey = household.errorKey ?? "household.loadError" }
            return
        }
        guard generation == ticket else { return }
        if case SessionFailure.rejected(404, "household_not_found") = error {
            detail = nil; history = []; sheet = nil; detailMissing = openedRef != nil; errorKey = "sharedPlan.deleted"
        } else { errorKey = Self.message(error) }
        let latest = await household.controller.snapshot()
        if latest.revision != identity?.revision || latest.phase != .authenticated { household.bind(latest); household.sessionChanged?(latest) }
    }
    static func message(_ error: Error) -> String {
        guard case SessionFailure.rejected(let status, let code) = error, status < 500 else { return "household.loadError" }
        switch code {
        case "budget_scope_conflict": return "budget.error.duplicate"
        case "shared_plan_scope_changed", "stale_version", "stale_activity", "shared_plan_stale": return "sharedPlan.changed"
        case "shared_plan_forbidden", "shared_plan_read_only", "shared_plan_owner_required": return "sharedPlan.permissionError"
        case "shared_plan_conflict", "activity_already_linked", "occurrence_already_linked": return "sharedPlan.linkedError"
        default: return "household.reviewError"
        }
    }
}

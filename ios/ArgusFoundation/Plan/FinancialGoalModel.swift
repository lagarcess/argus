import SwiftUI
import ArgusSession

struct FinancialGoalNavigation: Codable, Equatable {
    enum Origin: String, Codable { case home, plan, planOverview, search }
    var goalID: UUID
    var origin: Origin
    var activityID: UUID?
    var anchor: UUID?
    var anchorOffset: Double?
    var occurrenceID: String?
}

enum FinancialGoalAction: String, Identifiable { case allocation, link; var id: String { rawValue } }

@MainActor
final class FinancialGoalModel: ObservableObject {
    @Published private(set) var navigation: FinancialGoalNavigation?
    @Published private(set) var detail: FinancialGoalProgress?
    @Published private(set) var loading = false
    @Published private(set) var saving = false
    @Published private(set) var errorKey: String?
    @Published private(set) var candidates: [FinancialActivityDetail] = []
    @Published var draft: FinancialGoalDraft?
    @Published var action: FinancialGoalAction?
    private let controller: SessionController
    private unowned let loop: FinancialLoopModel
    private var identity: SessionSnapshot?
    private var request = UUID()
    private var generation = UUID()
    private let defaults: UserDefaults
    private let prefix = "financial.goal.navigation."

    init(controller: SessionController, loop: FinancialLoopModel, defaults: UserDefaults = .standard) {
        self.controller = controller; self.loop = loop; self.defaults = defaults
    }
    func bind(_ snapshot: SessionSnapshot?) {
        let next = snapshot?.phase == .authenticated ? snapshot : nil
        if let previous = identity?.profile?.id, previous != next?.profile?.id { defaults.removeObject(forKey: prefix + previous) }
        generation = UUID(); request = UUID(); identity = next
        detail = nil; draft = nil; action = nil; candidates = []; errorKey = nil; loading = false; saving = false; navigation = nil
        if let owner = next?.profile?.id, let bytes = defaults.data(forKey: prefix + owner) {
            navigation = try? JSONDecoder().decode(FinancialGoalNavigation.self, from: bytes)
        }
    }
    func open(_ id: UUID, origin: FinancialGoalNavigation.Origin, occurrenceId: String? = nil) async {
        navigation = .init(goalID: id, origin: origin, occurrenceID: occurrenceId); detail = nil; persist()
        await refreshIfOpen()
    }
    func refreshIfOpen() async {
        guard let identity, let navigation else { return }
        let ticket = UUID(); request = ticket; loading = true; errorKey = nil
        defer { if request == ticket { loading = false } }
        do {
            let next = try await controller.financialGoal(navigation.goalID, expectedIdentity: identity)
            guard request == ticket, self.identity == identity else { return }
            detail = next
        } catch {
            guard request == ticket, self.identity == identity else { return }
            detail = nil; errorKey = FinancialActivityEditor.message(error)
        }
    }
    func close() { request = UUID(); navigation = nil; detail = nil; errorKey = nil; persist() }
    func activity(_ id: UUID?, preservingScrollPosition: Bool = false) {
        navigation?.activityID = id
        if let id, !preservingScrollPosition { navigation?.anchor = id; navigation?.anchorOffset = nil }
        persist()
    }
    var scrollContext: FinancialScrollContext? {
        guard let navigation else { return nil }
        let ticket = generation
        return .init(id: ticket.uuidString + navigation.goalID.uuidString + navigation.origin.rawValue,
            anchor: navigation.anchor?.uuidString, offset: navigation.anchorOffset,
            availableAnchors: !loading && detail?.goal.id == navigation.goalID ? detail?.contributions.map { $0.activityId.uuidString } : nil,
            active: navigation.activityID == nil,
            remember: { [weak self] anchor, offset in
                guard let self, self.generation == ticket, !self.loading, let anchor = UUID(uuidString: anchor), offset.isFinite,
                      self.navigation?.goalID == navigation.goalID, self.navigation?.origin == navigation.origin,
                      self.navigation?.activityID == nil, self.detail?.contributions.contains(where: { $0.activityId == anchor }) == true,
                      self.navigation?.anchor != anchor || self.navigation?.anchorOffset != offset else { return }
                self.navigation?.anchor = anchor; self.navigation?.anchorOffset = offset; self.persist()
            })
    }
    func create() {
        guard loop.pendingConfirmation == nil, let projection = loop.plan.projection else { return }
        draft = FinancialGoalDraft(start: projection.startDate, currency: "DOP")
    }
    func edit() {
        guard loop.pendingConfirmation == nil, let detail else { return }
        draft = FinancialGoalDraft(goal: detail.goal)
    }
    func save(locale: Locale) async {
        guard let draft else { return }
        let ticket = generation
        do {
            let operation: FinancialPlanOperation = draft.existing.map { .editGoal(id: $0.id, version: $0.version) } ?? .createGoal
            try await perform(operation, command: draft.command(locale: locale))
            guard generation == ticket else { return }; self.draft = nil
        } catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func archive(_ archived: Bool) async {
        guard let goal = detail?.goal else { return }
        let ticket = generation
        do { try await perform(.editGoal(id: goal.id, version: goal.version), command: FinancialBudgetLifecycleCommand(expectedVersion: goal.version, archived: archived)) }
        catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func release(_ contribution: FinancialGoalContribution) async {
        guard let goal = detail?.goal else { return }
        let ticket = generation
        do { try await perform(.releaseGoal(id: goal.id, claimId: contribution.id, version: goal.version), command: FinancialGoalReleaseCommand(expectedVersion: goal.version)) }
        catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func allocate(_ command: FinancialGoalAllocationCommand) async {
        let ticket = generation
        do { try await perform(.allocateGoals, command: command); if generation == ticket { action = nil } }
        catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func loadCandidates() async {
        guard let identity, let goal = detail?.goal, loop.pendingConfirmation == nil else { return }
        let ticket = generation; let query = UUID(); request = query
        action = .link; candidates = []; loading = true; errorKey = nil
        defer { if request == query { loading = false } }
        do {
            let next = try await controller.financialGoalCandidates(goal.id, expectedIdentity: identity)
            guard generation == ticket, request == query else { return }
            candidates = next.items
        } catch { if generation == ticket, request == query { errorKey = FinancialActivityEditor.message(error) } }
    }
    func link(_ entry: FinancialActivityDetail, treatment: String, occurrenceID: String?) async {
        guard let goal = detail?.goal, let projection = loop.plan.projection else { return }
        let ticket = generation
        let versions = projection.accounts.reduce(into: [String: Int]()) { $0[$1.id.uuidString] = $1.version }
        do {
            try await perform(.linkGoal(id: goal.id, version: goal.version), command: FinancialGoalLinkCommand(expectedVersion: goal.version,
                activityId: entry.activityId, activityRevision: entry.revision, treatment: treatment, occurrenceId: occurrenceID, expectedAccountVersions: versions))
            if generation == ticket { action = nil }
        } catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func record() {
        guard let goal = detail?.goal, let projection = loop.plan.projection,
              let account = projection.accounts.first(where: { $0.id == goal.contributionPlan?.sourceAccountId }) ?? projection.accounts.first(where: { $0.id == goal.destinationAccountId }) else { return }
        loop.record(account, goal: goal, goalOccurrenceId: navigation?.occurrenceID)
    }
    func confirmed(_ operation: FinancialPlanOperation) {
        switch operation {
        case .createGoal, .editGoal: draft = nil
        case .allocateGoals, .linkGoal, .releaseGoal: action = nil
        default: break
        }
    }
    private func perform<Command: Encodable>(_ operation: FinancialPlanOperation, command: Command) async throws {
        guard !saving else { return }
        let ticket = generation; saving = true; errorKey = nil
        defer { if generation == ticket { saving = false } }
        try await loop.confirmPlan(operation, command: command, originAccountId: detail?.goal.destinationAccountId)
        guard generation == ticket else { throw SessionFailure.staleOperation }
    }
    private func persist() {
        guard let owner = identity?.profile?.id else { return }
        if let navigation, let bytes = try? JSONEncoder().encode(navigation) { defaults.set(bytes, forKey: prefix + owner) }
        else { defaults.removeObject(forKey: prefix + owner) }
    }
}

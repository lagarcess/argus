import SwiftUI
import ArgusSession

struct FinancialDebtNavigation: Codable, Equatable {
    enum Origin: String, Codable { case home, plan, planOverview, search, account, searchAccount }
    var debtID: UUID
    var origin: Origin
    var activityID: UUID?
    var anchor: UUID?
    var occurrenceID: String?
}

@MainActor
final class FinancialDebtModel: ObservableObject {
    @Published private(set) var navigation: FinancialDebtNavigation?
    @Published private(set) var detail: FinancialDebtProgress?
    @Published private(set) var loading = false
    @Published private(set) var saving = false
    @Published private(set) var errorKey: String?
    @Published private(set) var candidates: [FinancialActivityDetail] = []
    @Published var draft: FinancialDebtDraft?
    @Published var choosingAccount = false
    @Published var linking = false
    @Published var occurrenceID: String?
    private let controller: SessionController
    private unowned let loop: FinancialLoopModel
    private var identity: SessionSnapshot?
    private var generation = UUID()
    private var request = UUID()
    private let defaults: UserDefaults
    private var chosenAccount: FinancialAccount?
    private let prefix = "financial.debt.navigation."

    init(controller: SessionController, loop: FinancialLoopModel, defaults: UserDefaults = .standard) {
        self.controller = controller; self.loop = loop; self.defaults = defaults
    }
    func bind(_ snapshot: SessionSnapshot?) {
        let next = snapshot?.phase == .authenticated ? snapshot : nil
        if let previous = identity?.profile?.id, previous != next?.profile?.id { defaults.removeObject(forKey: prefix + previous) }
        identity = next; generation = UUID(); request = UUID()
        detail = nil; navigation = nil; draft = nil; candidates = []; errorKey = nil
        choosingAccount = false; chosenAccount = nil; linking = false; loading = false; saving = false; occurrenceID = nil
        if let owner = next?.profile?.id, let bytes = defaults.data(forKey: prefix + owner) {
            navigation = try? JSONDecoder().decode(FinancialDebtNavigation.self, from: bytes)
        }
    }
    func open(_ id: UUID, origin: FinancialDebtNavigation.Origin, occurrenceId: String? = nil) async {
        navigation = .init(debtID: id, origin: origin, occurrenceID: occurrenceId); detail = nil; persist()
        await refreshIfOpen()
    }
    func refreshIfOpen() async {
        guard let identity, let navigation else { return }
        let ticket = UUID(); request = ticket; loading = true; errorKey = nil
        defer { if request == ticket { loading = false } }
        do {
            let next = try await controller.financialDebt(navigation.debtID, expectedIdentity: identity)
            guard request == ticket, self.identity == identity else { return }
            detail = next
            occurrenceID = navigation.occurrenceID ?? next.occurrences.first(where: { $0.status != .fulfilled })?.id
        } catch {
            guard request == ticket, self.identity == identity else { return }
            detail = nil; errorKey = FinancialActivityEditor.message(error)
        }
    }
    func close() { request = UUID(); navigation = nil; detail = nil; errorKey = nil; persist() }
    func activity(_ id: UUID?) { navigation?.activityID = id; if let id { navigation?.anchor = id }; persist() }
    func chooseOccurrence(_ id: String?) { occurrenceID = id; navigation?.occurrenceID = id; persist() }
    func create(_ account: FinancialAccount? = nil) {
        guard loop.pendingConfirmation == nil, let projection = loop.plan.projection else { return }
        if let account {
            choosingAccount = false; draft = FinancialDebtDraft(account: account, start: projection.startDate)
        } else { choosingAccount = true }
    }
    func chooseAccount(_ account: FinancialAccount) { chosenAccount = account; choosingAccount = false }
    func accountChooserDismissed() {
        guard let account = chosenAccount else { return }; chosenAccount = nil; create(account)
    }
    func edit() {
        guard loop.pendingConfirmation == nil, let debt = detail?.debt else { return }
        draft = FinancialDebtDraft(debt: debt)
    }
    func save(locale: Locale) async {
        guard let draft else { return }
        let ticket = generation
        do {
            let operation: FinancialPlanOperation = draft.existing.map { .editDebt(id: $0.id, version: $0.version) } ?? .createDebt
            try await perform(operation, command: draft.command(locale: locale))
            if generation == ticket { self.draft = nil }
        } catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func archive(_ archived: Bool) async {
        guard let debt = detail?.debt else { return }
        let ticket = generation
        do { try await perform(.editDebt(id: debt.id, version: debt.version), command: FinancialBudgetLifecycleCommand(expectedVersion: debt.version, archived: archived)) }
        catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func loadCandidates() async {
        guard let identity, let debt = detail?.debt, loop.pendingConfirmation == nil else { return }
        let ticket = generation; let query = UUID(); request = query
        linking = true; candidates = []; loading = true; errorKey = nil
        defer { if request == query { loading = false } }
        do {
            let next = try await controller.financialDebtCandidates(debt.id, expectedIdentity: identity)
            guard generation == ticket, request == query else { return }
            candidates = next.items
        } catch { if generation == ticket, request == query { errorKey = FinancialActivityEditor.message(error) } }
    }
    func link(_ entry: FinancialActivityDetail) async {
        guard let debt = detail?.debt, let projection = loop.plan.projection else { return }
        let ticket = generation
        let versions = projection.accounts.reduce(into: [String: Int]()) { $0[$1.id.uuidString] = $1.version }
        do {
            try await perform(.linkDebt(id: debt.id, version: debt.version), command: FinancialDebtLinkCommand(expectedVersion: debt.version, activityId: entry.activityId, activityRevision: entry.revision, occurrenceId: occurrenceID, expectedAccountVersions: versions))
            if generation == ticket { linking = false }
        } catch { if generation == ticket { errorKey = FinancialActivityEditor.message(error) } }
    }
    func record(extra: Bool = false) {
        guard let debt = detail?.debt, let origin = loop.plan.projection?.accounts.first(where: { $0.id == debt.sourceAccountId }) else { return }
        loop.record(origin, debt: debt, debtOccurrenceId: extra ? nil : occurrenceID)
    }
    func confirmed(_ operation: FinancialPlanOperation) {
        switch operation { case .createDebt, .editDebt: draft = nil; case .linkDebt: linking = false; default: break }
    }
    private func perform<Command: Encodable>(_ operation: FinancialPlanOperation, command: Command) async throws {
        guard !saving else { return }
        let ticket = generation; saving = true; errorKey = nil
        defer { if generation == ticket { saving = false } }
        try await loop.confirmPlan(operation, command: command, originAccountId: detail?.debt.sourceAccountId)
        guard generation == ticket else { throw SessionFailure.staleOperation }
    }
    private func persist() {
        guard let owner = identity?.profile?.id else { return }
        if let navigation, let bytes = try? JSONEncoder().encode(navigation) { defaults.set(bytes, forKey: prefix + owner) }
        else { defaults.removeObject(forKey: prefix + owner) }
    }
}

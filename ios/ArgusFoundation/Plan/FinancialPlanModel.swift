import SwiftUI
import ArgusSession

@MainActor
final class FinancialPlanModel: ObservableObject {
    @Published private(set) var projection: FinancialPlanProjection?
    @Published private(set) var loading = false
    @Published private(set) var saving = false
    @Published private(set) var loadingDetails = false
    @Published private(set) var errorKey: String?
    @Published var draft: FinancialExpectationDraft?
    @Published var selectedOccurrence: FinancialPlanOccurrence?
    @Published private(set) var candidates: [FinancialActivityDetail] = []
    @Published private(set) var linkedActivity: FinancialActivityDetail?
    private let controller: SessionController
    private let accounts: AccountsModel
    private unowned let loop: FinancialLoopModel
    private var identity: SessionSnapshot?
    private var generation = UUID()
    private var request = UUID()
    private var detailRequest = UUID()
    private var endDate: String?
    private enum AfterOccurrence { case record(FinancialPlanOccurrence), edit(FinancialExpectation), correct(FinancialActivityDetail) }
    private var afterOccurrence: AfterOccurrence?

    init(controller: SessionController, accounts: AccountsModel, loop: FinancialLoopModel) {
        self.controller = controller; self.accounts = accounts; self.loop = loop
    }

    func bind(_ snapshot: SessionSnapshot?) {
        generation = UUID(); request = UUID(); detailRequest = UUID()
        identity = snapshot?.phase == .authenticated ? snapshot : nil
        projection = nil; draft = nil; selectedOccurrence = nil; candidates = []; linkedActivity = nil
        endDate = nil; afterOccurrence = nil; loading = false; loadingDetails = false; saving = false; errorKey = nil
    }

    func refresh(until: String? = nil) async {
        guard let identity else { return }
        if let until { endDate = until }
        let ticket = generation; let query = UUID(); request = query
        loading = true; errorKey = nil
        defer { if generation == ticket, request == query { loading = false } }
        do {
            let next = try await controller.financialPlan(endDate: endDate, expectedIdentity: identity)
            guard generation == ticket, request == query else { return }
            projection = next
            loop.acceptPlanHome(next.home)
            if let selectedOccurrence { self.selectedOccurrence = next.occurrences.first { $0.id == selectedOccurrence.id } }
        } catch { if request == query { await failed(error, ticket: ticket) } }
    }

    func create() {
        guard loop.pendingConfirmation == nil, let projection else { return }
        errorKey = nil
        draft = FinancialExpectationDraft(startDate: projection.startDate, currency: projection.accounts.first?.currency ?? "DOP")
    }

    func edit(_ expectation: FinancialExpectation) {
        guard loop.pendingConfirmation == nil else { return }
        errorKey = nil; draft = FinancialExpectationDraft(expectation: expectation)
    }

    func save(locale: Locale) async {
        guard let draft, !saving, let identity else { return }
        let ticket = generation; saving = true; errorKey = nil
        defer { if generation == ticket { saving = false } }
        do {
            let command = try draft.command(locale: locale)
            let operation: FinancialPlanOperation = draft.existing.map { .editExpectation(id: $0.id, version: $0.version) } ?? .createExpectation
            try await loop.confirmPlan(operation, command: command, originAccountId: draft.accountId)
            guard generation == ticket, self.identity == identity else { return }
            self.draft = nil
        } catch { await failed(error, ticket: ticket) }
    }

    func selectAccounts(_ ids: Set<UUID>, timeZone: String) async -> Bool {
        guard let projection, !saving else { return false }
        let ticket = generation; saving = true; errorKey = nil
        defer { if generation == ticket { saving = false } }
        do {
            let version = projection.selection.version
            try await loop.confirmPlan(.selection(version: version), command: FinancialPlanSelectionCommand(
                expectedVersion: version, accountIds: ids.sorted { $0.uuidString < $1.uuidString }, timeZone: timeZone), originAccountId: ids.first)
            return generation == ticket
        } catch { await failed(error, ticket: ticket); return false }
    }

    func open(_ occurrence: FinancialPlanOccurrence) async {
        guard let identity else { return }
        selectedOccurrence = occurrence; linkedActivity = nil; candidates = []; errorKey = nil
        let ticket = generation; let query = UUID(); detailRequest = query
        loadingDetails = occurrence.activityId != nil
        defer { if generation == ticket, detailRequest == query { loadingDetails = false } }
        if let id = occurrence.activityId {
            do {
                let detail = try await controller.financialActivityDetail(id, expectedIdentity: identity)
                guard generation == ticket, detailRequest == query else { return }
                linkedActivity = detail
            } catch { await failed(error, ticket: ticket) }
        }
    }

    func loadCandidates(_ occurrence: FinancialPlanOccurrence) async {
        guard let identity else { return }
        let ticket = generation; let query = UUID(); detailRequest = query
        candidates = []; errorKey = nil; loadingDetails = true
        defer { if generation == ticket, detailRequest == query { loadingDetails = false } }
        do {
            let next = try await controller.financialPlanCandidates(occurrenceId: occurrence.id, expectedIdentity: identity)
            guard generation == ticket, detailRequest == query else { return }
            candidates = next.items
        } catch { await failed(error, ticket: ticket) }
    }

    func link(_ activity: FinancialActivityDetail, to occurrence: FinancialPlanOccurrence) async -> Bool {
        guard !saving else { return false }
        let ticket = generation; saving = true; errorKey = nil
        defer { if generation == ticket { saving = false } }
        do {
            try await loop.confirmPlan(.link(occurrenceId: occurrence.id, version: occurrence.expectationVersion), command:
                FinancialPlanLinkCommand(expectedVersion: occurrence.expectationVersion, activityId: activity.activityId,
                                         activityRevision: activity.revision), originAccountId: occurrence.accountId)
            guard generation == ticket else { return false }
            selectedOccurrence = nil; candidates = []; linkedActivity = nil
            return true
        } catch { await failed(error, ticket: ticket); return false }
    }

    func record(_ occurrence: FinancialPlanOccurrence) {
        afterOccurrence = .record(occurrence); selectedOccurrence = nil
    }

    func editFromOccurrence(_ expectation: FinancialExpectation) {
        afterOccurrence = .edit(expectation); selectedOccurrence = nil
    }

    func correctLinked() {
        guard let activity = linkedActivity else { return }
        afterOccurrence = .correct(activity); selectedOccurrence = nil
    }

    func occurrenceDismissed() {
        guard let action = afterOccurrence, identity != nil else { return }
        afterOccurrence = nil
        switch action {
        case .edit(let expectation): edit(expectation)
        case .record(let occurrence):
            guard let account = projection?.accounts.first(where: { $0.id == occurrence.accountId }) else { return }
            loop.record(account, occurrence: occurrence)
        case .correct(let activity):
            guard let id = activity.legs.first?.accountId,
                  let account = accounts.accounts.first(where: { $0.id == id }) else { return }
            linkedActivity = nil
            loop.record(account, correcting: activity)
        }
    }

    func confirmed(_ operation: FinancialPlanOperation) {
        switch operation {
        case .createExpectation, .editExpectation: draft = nil
        case .link: selectedOccurrence = nil; candidates = []; linkedActivity = nil
        default: break
        }
    }

    private func failed(_ error: Error, ticket: UUID) async {
        guard generation == ticket else { return }
        let current = await controller.snapshot()
        guard generation == ticket else { return }
        if current != identity { loop.bind(current); loop.sessionChanged?(current) }
        else { errorKey = FinancialActivityEditor.message(error) }
    }
}

@MainActor
final class FinancialExpectationDraft: ObservableObject, Identifiable {
    let id = UUID()
    let existing: FinancialExpectation?
    @Published var kind: FinancialExpectationKind = .bill
    @Published var title = ""
    @Published var currency: String
    @Published var amount = ""
    @Published var accountId: UUID?
    @Published var date: Date
    @Published var cadence = FinancialPlanSchedule.Cadence.once
    @Published var firstMonthDay = 15
    @Published var secondMonthDay = 31
    @Published var hasEnd = false
    @Published var end: Date
    @Published var effectiveDate: Date

    init(startDate: String, currency: String) {
        existing = nil; self.currency = currency
        let start = PlanPresentation.date(startDate)
        date = start; end = start; effectiveDate = start
    }
    init(expectation: FinancialExpectation) {
        existing = expectation; kind = expectation.kind; title = expectation.title; currency = expectation.currency
        amount = AccountPresentation.amount(expectation.amount, locale: .current); accountId = expectation.accountId
        date = PlanPresentation.date(expectation.schedule.startDate); cadence = expectation.schedule.cadence
        firstMonthDay = expectation.schedule.monthDays.first ?? PlanPresentation.monthDay(expectation.schedule.startDate)
        secondMonthDay = expectation.schedule.monthDays.last ?? 31
        hasEnd = expectation.schedule.endDate != nil
        end = PlanPresentation.date(expectation.schedule.endDate ?? expectation.schedule.startDate)
        effectiveDate = PlanPresentation.date(expectation.earliestEffectiveDate)
    }
    var ready: Bool { !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && title.count <= 100 && !amount.isEmpty }
    var schedule: FinancialPlanSchedule {
        .init(cadence: cadence, startDate: PlanPresentation.day(date), endDate: hasEnd ? PlanPresentation.day(end) : nil,
              monthDays: cadence == .twiceMonthly ? [firstMonthDay, secondMonthDay] : cadence == .monthly ? monthlyDays : [])
    }
    private var monthlyDays: [Int] {
        if let existing, existing.schedule.monthDays.isEmpty,
           firstMonthDay == PlanPresentation.monthDay(PlanPresentation.day(date)) { return [] }
        return [firstMonthDay]
    }
    var scheduleChanged: Bool { existing.map { $0.schedule != schedule } ?? false }
    var structuralChange: Bool { existing.map { $0.accountId != accountId || scheduleChanged } ?? false }
    func command(locale: Locale) throws -> FinancialExpectationCommand {
        guard ready, let exact = try AccountEntry.amount(amount, locale: locale) else { throw AccountEntry.Failure.amount }
        return .init(kind: existing == nil ? kind : nil, title: title, currency: existing == nil ? currency : nil,
            amount: exact, accountId: accountId, includesAccount: existing == nil || existing?.accountId != accountId, schedule: existing == nil || scheduleChanged ? schedule : nil,
            expectedVersion: existing?.version, effectiveDate: structuralChange ? PlanPresentation.day(effectiveDate) : nil)
    }
}

enum PlanPresentation {
    static func monthDay(_ value: String) -> Int { Int(value.suffix(2)) ?? 1 }
    static func date(_ value: String) -> Date {
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0); formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: value) ?? .distantPast
    }
    static func day(_ date: Date) -> String {
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0); formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
    static func dateLabel(_ value: String, locale: Locale) -> String {
        let formatter = DateFormatter(); formatter.locale = locale; formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateStyle = .medium
        return formatter.string(from: date(value))
    }
    static func money(_ minor: String, currency: String, digits: Int, locale: Locale) -> String {
        currency + " " + AccountPresentation.amount(AccountPresentation.decimal(minor, digits: digits), locale: locale)
    }
}

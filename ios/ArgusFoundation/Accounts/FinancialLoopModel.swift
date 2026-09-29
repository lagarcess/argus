import SwiftUI
import ArgusSession

@MainActor
final class FinancialLoopModel: ObservableObject {
    @Published private(set) var home: FinancialHome?
    @Published private(set) var activity: [FinancialActivity] = []
    @Published private(set) var checks: [FinancialCheck] = []
    @Published private(set) var activityCursor: String?
    @Published private(set) var checksCursor: String?
    @Published private(set) var loadingMore = false
    @Published private(set) var errorKey: String?
    @Published private(set) var loading = false
    @Published var editor: FinancialEditor?
    private let controller: SessionController
    private let accounts: AccountsModel
    private var identity: SessionSnapshot?
    private var generation = UUID()
    private var homeRequest = UUID()
    private var detailRequest = UUID()
    var sessionChanged: ((SessionSnapshot) -> Void)?

    init(controller: SessionController, accounts: AccountsModel) {
        self.controller = controller; self.accounts = accounts
    }

    func bind(_ snapshot: SessionSnapshot?) {
        guard identity?.revision != snapshot?.revision || identity?.profile?.id != snapshot?.profile?.id || identity?.phase != snapshot?.phase else { return }
        generation = UUID(); identity = snapshot?.phase == .authenticated ? snapshot : nil
        home = nil; activity = []; checks = []; activityCursor = nil; checksCursor = nil; loadingMore = false; editor = nil; errorKey = nil; loading = false
    }

    func refresh() async {
        guard let identity else { return }
        let ticket = generation
        let request = UUID(); homeRequest = request
        loading = true; errorKey = nil
        defer { if generation == ticket && homeRequest == request { loading = false } }
        do {
            let next = try await controller.financialHome(expectedIdentity: identity)
            guard generation == ticket, homeRequest == request else { return }
            home = next
        } catch { if homeRequest == request { await handle(error, ticket: ticket) } }
    }

    func open(_ account: FinancialAccount) async {
        guard let identity else { return }
        let ticket = generation
        let request = UUID(); detailRequest = request
        activity = []; checks = []; activityCursor = nil; checksCursor = nil; errorKey = nil
        do {
            let entries = try await controller.financialActivity(accountId: account.id, expectedIdentity: identity)
            let observations = try await controller.financialChecks(accountId: account.id, expectedIdentity: identity)
            guard generation == ticket, detailRequest == request, accounts.selected?.id == account.id else { return }
            activity = entries.items; checks = observations.items
            activityCursor = entries.nextCursor; checksCursor = observations.nextCursor
        } catch { if detailRequest == request { await handle(error, ticket: ticket) } }
    }

    func more(_ account: FinancialAccount, checks: Bool) async {
        guard let identity, !loadingMore else { return }
        let ticket = generation; let detail = detailRequest
        loadingMore = true
        defer { if generation == ticket { loadingMore = false } }
        do {
            if checks, let cursor = checksCursor {
                let page = try await controller.financialChecks(accountId: account.id, cursor: cursor, expectedIdentity: identity)
                guard generation == ticket, detailRequest == detail else { return }
                self.checks += page.items; checksCursor = page.nextCursor
            } else if let cursor = activityCursor {
                let page = try await controller.financialActivity(accountId: account.id, cursor: cursor, expectedIdentity: identity)
                guard generation == ticket, detailRequest == detail else { return }
                activity += page.items; activityCursor = page.nextCursor
            }
        } catch { await handle(error, ticket: ticket) }
    }

    func history(_ account: FinancialAccount, activity: FinancialActivity) async throws -> [FinancialActivity] {
        guard let identity else { throw SessionFailure.unauthorized }
        let ticket = generation
        var entries: [FinancialActivity] = []; var cursor: String?
        repeat {
            let page = try await controller.financialActivityHistory(accountId: account.id, recordId: activity.recordId, cursor: cursor, expectedIdentity: identity)
            guard generation == ticket else { throw SessionFailure.staleOperation }
            entries += page.items; cursor = page.nextCursor
        } while cursor != nil
        return entries
    }

    func expense(_ account: FinancialAccount, correcting activity: FinancialActivity? = nil) {
        guard let identity else { return }
        let ticket = generation
        editor = FinancialEditor(account: account, kind: .expense(activity), controller: controller, identity: identity, retired: { [weak self] snapshot in
            guard let self, self.generation == ticket else { return }
            self.bind(snapshot); self.sessionChanged?(snapshot)
        }) { [weak self] account in
            await self?.accepted(account, ticket: ticket)
        }
    }

    func check(_ account: FinancialAccount) {
        guard let identity else { return }
        let ticket = generation
        editor = FinancialEditor(account: account, kind: .check, controller: controller, identity: identity, retired: { [weak self] snapshot in
            guard let self, self.generation == ticket else { return }
            self.bind(snapshot); self.sessionChanged?(snapshot)
        }) { [weak self] account in
            await self?.accepted(account, ticket: ticket)
        }
    }

    private func accepted(_ account: FinancialAccount, ticket: UUID) async {
        guard generation == ticket, identity != nil else { return }
        accounts.accept(account)
        editor = nil
        await refresh()
        await open(account)
    }

    private func handle(_ error: Error, ticket: UUID) async {
        guard generation == ticket else { return }
        let snapshot = await controller.snapshot()
        guard generation == ticket else { return }
        if snapshot.revision != identity?.revision || snapshot.phase != .authenticated {
            bind(snapshot); sessionChanged?(snapshot)
        } else { errorKey = FinancialEditor.message(error) }
    }
}

@MainActor
final class FinancialEditor: ObservableObject, Identifiable {
    enum Kind { case expense(FinancialActivity?), check }
    enum Phase { case editing, loading, review, saving, uncertain, conflict, retired, saved }
    let id = UUID()
    let account: FinancialAccount
    let kind: Kind
    @Published var amount = "" { didSet { if amount != oldValue { invalidatePlacement() } } }
    @Published var note = ""
    @Published var reason = ""
    @Published var date = Date() { didSet { if date != oldValue { invalidatePlacement() } } }
    @Published private(set) var categories: [FinancialCategory] = []
    @Published var categoryId: String?
    @Published private(set) var phase = Phase.editing
    @Published private(set) var expensePreview: ExpensePreview?
    @Published private(set) var checkPreview: BalanceCheckPreview?
    @Published private(set) var errorKey: String?
    private var coverage: [FinancialCoverage] = []
    private var expenseRequest: ExpenseRequest?
    private var checkRequest: BalanceCheckRequest?
    private var key = UUID()
    private let controller: SessionController
    private let identity: SessionSnapshot
    private let retired: (SessionSnapshot) -> Void
    private let completed: (FinancialAccount) async -> Void
    private let timeZone: String

    init(account: FinancialAccount, kind: Kind, controller: SessionController, identity: SessionSnapshot, retired: @escaping (SessionSnapshot) -> Void = { _ in },
         completed: @escaping (FinancialAccount) async -> Void) {
        self.account = account; self.kind = kind; self.controller = controller
        self.identity = identity; self.retired = retired; self.completed = completed
        if case .expense(let activity) = kind, let activity {
            amount = AccountPresentation.amount(activity.amount, locale: .current)
            note = activity.note ?? ""; categoryId = activity.categoryId; coverage = activity.coverage
            date = AccountPresentation.parseDate(activity.occurredAt) ?? Date()
            timeZone = activity.timeZone
        } else { timeZone = TimeZone.current.identifier }
    }

    var isCorrection: Bool { if case .expense(let value) = kind { return value != nil }; return false }
    var isCheck: Bool { if case .check = kind { return true }; return false }
    var busy: Bool { phase == .loading || phase == .saving }
    var canEdit: Bool { phase == .editing || (phase == .review && expensePreview?.ready == false) }
    var canConfirm: Bool { phase == .uncertain || (phase == .review && (checkPreview != nil || expensePreview?.ready == true)) }
    var readyToReview: Bool { !amount.isEmpty && (!isCorrection || !reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) }

    func loadCategories() async {
        guard !isCheck else { return }
        do { categories = try await controller.financialCategories(expectedIdentity: identity).categories }
        catch { /* Optional categorization must not block recording. */ }
    }

    private func invalidatePlacement() {
        guard canEdit, !busy else { return }
        coverage = []; expensePreview = nil; expenseRequest = nil
    }

    func edit() {
        guard phase == .review else { return }
        phase = .editing; expensePreview = nil; checkPreview = nil; expenseRequest = nil; checkRequest = nil
    }

    func answer(_ observation: UUID, included: Bool) {
        guard !busy, phase != .uncertain else { return }
        coverage.removeAll { $0.observationId == observation }
        coverage.append(.init(observationId: observation, included: included))
        phase = .editing; expensePreview = nil
    }

    func review(locale: Locale) async {
        guard !busy, phase != .uncertain else { return }
        phase = .loading; errorKey = nil
        do {
            guard let exact = try AccountEntry.amount(amount, locale: locale) else { throw AccountEntry.Failure.amount }
            let formatter = ISO8601DateFormatter()
            formatter.timeZone = TimeZone(identifier: timeZone)
            switch kind {
            case .expense(let activity):
                var request = ExpenseRequest(expectedVersion: account.version, amount: exact, occurredAt: formatter.string(from: date),
                                             timeZone: timeZone, note: note, categoryId: categoryId, coverage: coverage,
                                             expectedRevision: activity?.revision, reason: isCorrection ? reason : nil)
                let preview = try await controller.expensePreview(accountId: account.id, recordId: activity?.recordId,
                                                                  request: request, expectedIdentity: identity)
                request.previewToken = preview.previewToken
                expenseRequest = request; expensePreview = preview
            case .check:
                var request = BalanceCheckRequest(expectedVersion: account.version, amount: exact, asOf: formatter.string(from: date),
                                                  timeZone: timeZone, note: note)
                let preview = try await controller.balanceCheckPreview(accountId: account.id, request: request, expectedIdentity: identity)
                request.previewToken = preview.previewToken
                checkRequest = request; checkPreview = preview
            }
            phase = .review
        } catch {
            if await retireIfNeeded() { return }
            resetRejectedPlacement(error)
            errorKey = Self.message(error)
            phase = Self.isConflict(error) ? .conflict : .editing
        }
    }

    func confirm() async {
        guard canConfirm else { return }
        phase = .saving; errorKey = nil
        do {
            let account: FinancialAccount
            switch kind {
            case .expense(let activity):
                guard let request = expenseRequest else { phase = .editing; return }
                account = try await controller.saveExpense(accountId: self.account.id, recordId: activity?.recordId,
                                                            request: request, key: key, expectedIdentity: identity).account
            case .check:
                guard let request = checkRequest else { phase = .editing; return }
                account = try await controller.saveBalanceCheck(accountId: self.account.id, request: request,
                                                                 key: key, expectedIdentity: identity).account
            }
            phase = .saved
            await completed(account)
        } catch {
            if await retireIfNeeded() { return }
            resetRejectedPlacement(error)
            errorKey = Self.message(error)
            if Self.isConflict(error) { phase = .conflict }
            else if case SessionFailure.rejected(let status, _) = error, (400..<500).contains(status), status != 408 { phase = .editing }
            else { phase = .uncertain }
        }
    }

    private func resetRejectedPlacement(_ error: Error) {
        guard case SessionFailure.rejected(_, let code) = error,
              code == "coverage_invalid" || code == "coverage_conflict" else { return }
        coverage = []; expensePreview = nil; expenseRequest = nil
    }

    private func retireIfNeeded() async -> Bool {
        let current = await controller.snapshot()
        guard current.phase != .authenticated || current.revision != identity.revision || current.profile?.id != identity.profile?.id else { return false }
        phase = .retired
        retired(current)
        return true
    }

    private static func isConflict(_ error: Error) -> Bool {
        if case SessionFailure.rejected(let status, _) = error { return status == 409 }
        return false
    }
    static func message(_ error: Error) -> String {
        if error is AccountEntry.Failure { return "accounts.error.amount_invalid" }
        guard case SessionFailure.rejected(_, let code) = error else { return "loop.error.connection" }
        let supported = ["stale_version", "amount_precision", "amount_invalid", "amount_out_of_range", "date_in_future", "reason_required", "reason_invalid"]
        if let code, supported.contains(code) { return "accounts.error." + code }
        if code == "check_before_latest_observation" { return "loop.error.checkDate" }
        if code == "coverage_conflict" { return "loop.error.coverage" }
        return "loop.error.validation"
    }
}

import SwiftUI
import ArgusSession

/// One editor for every supported money activity. The server owns eligibility,
/// reviewed effects, coverage questions and every balance calculation.
@MainActor
final class FinancialActivityEditor: ObservableObject, Identifiable {
    enum Phase { case editing, loading, review, saving, uncertain, conflict, retired, saved }

    let id = UUID()
    let origin: FinancialAccount
    let correcting: FinancialActivityDetail?
    @Published private(set) var kind: FinancialActivityKind
    @Published var accountId: UUID? { didSet { changed(accountId != oldValue) } }
    @Published var sourceAccountId: UUID? { didSet { changed(sourceAccountId != oldValue) } }
    @Published var destinationAccountId: UUID? { didSet { changed(destinationAccountId != oldValue) } }
    @Published var amount = "" { didSet { changed(amount != oldValue) } }
    @Published var note = "" { didSet { changed(note != oldValue) } }
    @Published var date = Date() { didSet { changed(date != oldValue) } }
    @Published var categoryId: String? { didSet { changed(categoryId != oldValue) } }
    @Published var sourceId: String? { didSet { changed(sourceId != oldValue) } }
    @Published var purchaseActivityId: UUID? { didSet { changed(purchaseActivityId != oldValue) } }
    @Published var reason = "" { didSet { changed(reason != oldValue) } }
    @Published private(set) var options: FinancialActivityOptions?
    @Published private(set) var purchases: [FinancialActivityDetail] = []
    @Published private(set) var preview: FinancialActivityPreview?
    @Published private(set) var phase = Phase.editing
    @Published private(set) var errorKey: String?

    private var answers: [FinancialAccountCoverage] = []
    private var reviewedCommand: FinancialActivityCommand?
    private var pendingWrite: PendingFinancialConfirmation?
    private var key = UUID()
    private let controller: SessionController
    private let journal: FinancialWriteJournal
    private let identity: SessionSnapshot
    private let timeZone: String
    private let started: (PendingFinancialConfirmation) -> Void
    private let resolved: () -> Void
    private let retired: (SessionSnapshot) -> Void
    private let completed: (FinancialActivityReceipt) async -> Void

    init(origin: FinancialAccount, correcting: FinancialActivityDetail? = nil,
         controller: SessionController, journal: FinancialWriteJournal, identity: SessionSnapshot,
         started: @escaping (PendingFinancialConfirmation) -> Void = { _ in },
         resolved: @escaping () -> Void = {},
         retired: @escaping (SessionSnapshot) -> Void = { _ in },
         completed: @escaping (FinancialActivityReceipt) async -> Void) {
        self.origin = origin; self.correcting = correcting
        self.controller = controller; self.journal = journal; self.identity = identity
        self.started = started; self.resolved = resolved; self.retired = retired; self.completed = completed
        kind = correcting?.kind ?? (origin.type == "credit_card" ? .cardPayment : origin.type == "investment" ? .transfer : .expense)
        timeZone = correcting?.timeZone ?? TimeZone.current.identifier
        if let correcting {
            amount = AccountPresentation.amount(correcting.amount, locale: .current)
            note = correcting.note ?? ""; categoryId = correcting.categoryId
            sourceId = correcting.sourceId; purchaseActivityId = correcting.purchaseActivityId
            date = AccountPresentation.parseDate(correcting.occurredAt) ?? Date()
            accountId = correcting.legs.first(where: { $0.role == "single" })?.accountId
            sourceAccountId = correcting.legs.first(where: { $0.role == "source" })?.accountId
            destinationAccountId = correcting.legs.first(where: { $0.role == "destination" })?.accountId
            answers = correcting.legs.flatMap { leg in
                leg.coverage.map { .init(accountId: leg.accountId, observationId: $0.observationId, included: $0.included) }
            }
        } else { setAccounts(for: kind) }
    }

    var isCorrection: Bool { correcting != nil }
    var busy: Bool { phase == .loading || phase == .saving }
    var canEdit: Bool { phase == .editing || (phase == .review && preview?.ready == false) }
    var canConfirm: Bool { phase == .uncertain || (phase == .review && preview?.ready == true && reviewedCommand != nil) }
    var readyToReview: Bool {
        !amount.isEmpty && note.unicodeScalars.count <= 200 &&
        (!isCorrection || !reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) &&
        (kind.isPaired ? sourceAccountId != nil && destinationAccountId != nil && sourceAccountId != destinationAccountId : accountId != nil)
    }

    var availableKinds: [FinancialActivityKind] {
        guard let options else { return [] }
        return FinancialActivityKind.allCases.filter { kind in
            options.eligibility[kind.rawValue]?.contains(origin.type) == true ||
            (kind.isPaired && options.destinationEligibility[kind.rawValue]?.contains(origin.type) == true)
        }
    }

    var singleChoices: [FinancialAccount] { choices(types: options?.eligibility[kind.rawValue]) }
    var sourceChoices: [FinancialAccount] {
        choices(types: options?.eligibility[kind.rawValue]).filter { $0.id != destinationAccountId }
    }
    var destinationChoices: [FinancialAccount] {
        choices(types: options?.destinationEligibility[kind.rawValue]).filter { $0.id != sourceAccountId }
    }
    var linkedPurchase: FinancialActivityDetail? { purchases.first { $0.activityId == purchaseActivityId } }

    func load() async {
        do {
            let loaded = try await controller.financialActivityOptions(expectedIdentity: identity)
            guard !(await retireIfNeeded()) else { return }
            options = loaded
            if !availableKinds.contains(kind), !isCorrection, let first = availableKinds.first { setKind(first) }
            if kind == .refund { await loadPurchases() }
        } catch {
            if await retireIfNeeded() { return }
            errorKey = Self.message(error)
        }
    }

    func setKind(_ next: FinancialActivityKind) {
        guard !isCorrection, canEdit, availableKinds.contains(next) || options == nil else { return }
        kind = next; categoryId = nil; sourceId = nil; purchaseActivityId = nil
        answers = []; invalidate(); setAccounts(for: next)
        if next == .refund { Task { await loadPurchases() } }
    }

    private func setAccounts(for kind: FinancialActivityKind) {
        if kind.isPaired {
            accountId = nil
            if kind == .cardPayment && origin.type == "credit_card" {
                sourceAccountId = nil; destinationAccountId = origin.id
            } else {
                sourceAccountId = origin.id; destinationAccountId = nil
            }
        } else {
            sourceAccountId = nil; destinationAccountId = nil; accountId = origin.id
        }
    }

    private func choices(types: [String]?) -> [FinancialAccount] {
        guard let options, let types else { return [] }
        return options.accounts.filter { !$0.archived && $0.currency == origin.currency && types.contains($0.type) }
    }

    private func loadPurchases() async {
        do {
            let loaded = try await controller.financialPurchases(currency: origin.currency, expectedIdentity: identity).items
            guard !(await retireIfNeeded()) else { return }
            purchases = loaded
        }
        catch { if !(await retireIfNeeded()) { errorKey = Self.message(error) } }
    }

    private func changed(_ different: Bool) {
        if different { invalidate() }
    }
    private func invalidate() {
        guard canEdit, !busy else { return }
        answers = []; preview = nil; reviewedCommand = nil
    }

    func edit() {
        guard phase == .review else { return }
        phase = .editing; preview = nil; reviewedCommand = nil
    }

    func answer(accountId: UUID, observationId: UUID, included: Bool) {
        guard !busy, phase != .uncertain else { return }
        answers.removeAll { $0.accountId == accountId && $0.observationId == observationId }
        answers.append(.init(accountId: accountId, observationId: observationId, included: included))
        phase = .editing; preview = nil; reviewedCommand = nil
    }

    func review(locale: Locale) async {
        guard !busy, phase != .uncertain else { return }
        phase = .loading; errorKey = nil
        do {
            guard readyToReview, let exact = try AccountEntry.amount(amount, locale: locale) else { throw AccountEntry.Failure.amount }
            let formatter = ISO8601DateFormatter()
            formatter.timeZone = TimeZone(identifier: timeZone)
            var ids = [accountId, sourceAccountId, destinationAccountId].compactMap { $0 }
            ids += correcting?.legs.map(\.accountId) ?? []
            ids += linkedPurchase?.legs.map(\.accountId) ?? []
            let versions = ids.reduce(into: [String: Int]()) { values, id in
                if let version = options?.accounts.first(where: { $0.id == id })?.version {
                    values[id.uuidString] = version
                }
            }
            let command = FinancialActivityCommand(kind: kind, accountId: kind.isPaired ? nil : accountId,
                sourceAccountId: kind.isPaired ? sourceAccountId : nil,
                destinationAccountId: kind.isPaired ? destinationAccountId : nil,
                amount: exact, occurredAt: formatter.string(from: date), timeZone: timeZone,
                note: note.isEmpty ? nil : note,
                categoryId: kind == .expense || (kind == .refund && purchaseActivityId == nil) ? categoryId : nil,
                sourceId: kind == .income ? sourceId : nil,
                purchaseActivityId: kind == .refund ? purchaseActivityId : nil,
                expectedRevision: correcting?.revision, reason: isCorrection ? reason : nil,
                expectedVersions: versions, coverage: answers)
            let next = try await controller.financialActivityPreview(command, activityId: correcting?.activityId,
                                                                      expectedIdentity: identity)
            guard !(await retireIfNeeded()) else { return }
            preview = next
            if next.ready, var reviewed = next.reviewedRequest, let token = next.previewToken {
                reviewed.previewToken = token
                reviewedCommand = reviewed
            } else { reviewedCommand = nil }
            phase = .review
        } catch {
            if await retireIfNeeded() { return }
            errorKey = Self.message(error)
            phase = Self.isConflict(error) ? .conflict : .editing
        }
    }

    func confirm() async {
        guard canConfirm else { return }
        if await retireIfNeeded() { return }
        phase = .saving; errorKey = nil
        do {
            let write: PendingFinancialConfirmation
            if let pendingWrite { write = pendingWrite }
            else {
                guard let reviewedCommand, let owner = identity.profile.flatMap({ UUID(uuidString: $0.id) }) else {
                    throw SessionFailure.invalidResponse
                }
                let encoder = JSONEncoder(); encoder.outputFormatting = .sortedKeys
                write = .init(ownerId: owner, originAccountId: origin.id, route: "financial-activities",
                              path: correcting.map { "/" + $0.activityId.uuidString } ?? "",
                              method: correcting == nil ? "POST" : "PATCH",
                              body: try encoder.encode(reviewedCommand), key: key)
                try journal.begin(write, for: identity)
                pendingWrite = write
                started(write)
            }
            let receipt = try await controller.sendFinancialConfirmation(write, expectedIdentity: identity)
            guard !(await retireIfNeeded()) else { return }
            try journal.clear(write, for: identity)
            pendingWrite = nil
            resolved()
            phase = .saved
            await completed(receipt)
        } catch {
            if await retireIfNeeded() { return }
            errorKey = Self.message(error)
            if Self.isDefinitive(error) {
                if let pendingWrite {
                    do { try journal.clear(pendingWrite, for: identity); self.pendingWrite = nil }
                    catch { phase = .uncertain; errorKey = Self.message(error); return }
                }
                resolved()
                key = UUID(); reviewedCommand = nil; preview = nil
                phase = Self.isConflict(error) ? .conflict : .editing
            } else { phase = .uncertain }
        }
    }

    private func retireIfNeeded() async -> Bool {
        let current = await controller.snapshot()
        guard current.phase != .authenticated || current.revision != identity.revision || current.profile?.id != identity.profile?.id else { return false }
        phase = .retired; retired(current); return true
    }

    private static func isConflict(_ error: Error) -> Bool {
        if case SessionFailure.rejected(let status, _) = error { return status == 409 }
        return error as? FinancialWriteJournalError == .pendingConfirmation
    }
    private static func isDefinitive(_ error: Error) -> Bool {
        if case SessionFailure.rejected(let status, _) = error { return (400..<500).contains(status) && status != 408 }
        return error as? FinancialWriteJournalError == .pendingConfirmation
    }
    static func message(_ error: Error) -> String {
        if error is AccountEntry.Failure { return "accounts.error.amount_invalid" }
        if let journal = error as? FinancialWriteJournalError {
            return journal == .pendingConfirmation ? "loop.pending.existing" : "auth.error.storage"
        }
        guard case SessionFailure.rejected(_, let code) = error else { return "loop.error.connection" }
        let known = ["stale_version", "stale_activity", "amount_precision", "amount_invalid", "amount_out_of_range",
                     "date_in_future", "reason_required", "reason_invalid", "account_ineligible", "same_account",
                     "currency_mismatch", "purchase_not_found", "refund_exceeds_purchase", "refund_before_purchase",
                     "purchase_has_refunds", "coverage_conflict"]
        if let code, known.contains(code) { return "loop.error." + code }
        return "loop.error.validation"
    }
}

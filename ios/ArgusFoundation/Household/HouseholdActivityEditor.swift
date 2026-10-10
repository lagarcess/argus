import SwiftUI
import ArgusSession

@MainActor
final class HouseholdActivityEditor: ObservableObject, Identifiable {
    let id = UUID()
    let household: Household
    let snapshot: HouseholdSnapshot
    let origin: HouseholdAccount
    let correcting: HouseholdActivity?
    @Published var kind: FinancialActivityKind = .expense { didSet { preview = nil; if kind != oldValue { category = nil; incomeSource = nil; purchase = nil; principal = ""; interest = ""; fees = "" } } }
    @Published var accountId: UUID? { didSet { preview = nil } }
    @Published var sourceId: UUID? { didSet { preview = nil } }
    @Published var destinationId: UUID? { didSet { preview = nil } }
    @Published var amount = "" { didSet { preview = nil } }
    @Published var principal = "" { didSet { preview = nil } }
    @Published var interest = "" { didSet { preview = nil } }
    @Published var fees = "" { didSet { preview = nil } }
    @Published var note = "" { didSet { preview = nil } }
    @Published var reason = "" { didSet { preview = nil } }
    @Published var category: String? { didSet { preview = nil } }
    @Published var incomeSource: String? { didSet { preview = nil } }
    @Published var purchase: UUID? { didSet { preview = nil } }
    @Published var date = Date() { didSet { preview = nil } }
    @Published var options: HouseholdActivityOptions?
    @Published private(set) var preview: FinancialActivityPreview?
    @Published private(set) var errorKey: String?
    @Published private(set) var busy = false
    private var coverage: [FinancialAccountCoverage] = []
    private let identity: SessionSnapshot
    private weak var model: HouseholdModel?
    init(model: HouseholdModel, identity: SessionSnapshot, household: Household, snapshot: HouseholdSnapshot, account: HouseholdAccount, correction: HouseholdActivity?) {
        self.model = model; self.identity = identity; self.household = household; self.snapshot = snapshot; origin = account; correcting = correction
        accountId = account.id; sourceId = account.id
        if let value = correction?.activity {
            kind = value.kind; amount = value.amount ?? ""; note = value.note ?? ""; category = value.categoryId; incomeSource = value.sourceId; purchase = value.purchaseActivityId
            accountId = value.legs.first(where: { $0.role == "single" })?.accountId
            sourceId = value.legs.first(where: { $0.role == "source" })?.accountId
            destinationId = value.legs.first(where: { $0.role == "destination" })?.accountId
            date = AccountPresentation.parseDate(value.occurredAt) ?? Date()
            let divisor = pow(Decimal(10), account.account.currencyFractionDigits)
            principal = value.principalMinor.map { (Decimal($0) / divisor).description } ?? ""
            interest = value.interestMinor.map { (Decimal($0) / divisor).description } ?? ""
            fees = value.feesMinor.map { (Decimal($0) / divisor).description } ?? ""
            coverage = value.legs.flatMap { leg in leg.coverage.map { FinancialAccountCoverage(accountId: leg.accountId, observationId: $0.observationId, included: $0.included) } }
        }
    }
    var current: Bool { model?.isAvailable == true && model?.selectedId == household.id && model?.household?.membershipId == household.membershipId && model?.identity?.revision == identity.revision && model?.editor?.id == id }
    var choices: [HouseholdFinancialAccount] { options?.accounts ?? [] }
    var kinds: [FinancialActivityKind] { FinancialActivityKind.allCases.filter { options?.eligibility[$0.rawValue]?.contains(origin.account.type) == true && $0 != .paymentReversal } }
    func load() async {
        guard let model, current else { return }
        do {
            let value = try await model.controller.householdResponse(HouseholdActivityOptions.self, path: model.path(household.id, "/activity-options"), expectedIdentity: identity)
            guard current else { return }; options = value
            if correcting == nil, !kinds.contains(kind), let first = kinds.first { kind = first }
        } catch {
            guard current else { return }
            if !(await model.resolveAccessFailure(error, householdId: household.id)), current { errorKey = "household.loadError" }
        }
    }
    func answer(_ accountId: UUID, _ observationId: UUID, _ included: Bool) {
        coverage.removeAll { $0.accountId == accountId && $0.observationId == observationId }
        coverage.append(FinancialAccountCoverage(accountId: accountId, observationId: observationId, included: included)); preview = nil
    }
    func review(_ locale: Locale) async {
        guard let model, current else { return }
        busy = true; errorKey = nil; defer { busy = false }
        do {
            let command = FinancialActivityCommand(kind: kind, accountId: kind.isPaired ? nil : accountId, sourceAccountId: kind.isPaired ? sourceId : nil, destinationAccountId: kind.isPaired ? destinationId : nil, amount: try AccountEntry.amount(amount, locale: locale) ?? "", occurredAt: ISO8601DateFormatter().string(from: date), timeZone: correcting?.activity.timeZone ?? TimeZone.current.identifier, note: note.isEmpty ? nil : note, categoryId: category, sourceId: incomeSource, purchaseActivityId: purchase, expectedRevision: correcting?.activity.revision, reason: reason.isEmpty ? nil : reason, coverage: coverage, principal: principal.isEmpty ? nil : try AccountEntry.amount(principal, locale: locale), interest: interest.isEmpty ? nil : try AccountEntry.amount(interest, locale: locale), fees: fees.isEmpty ? nil : try AccountEntry.amount(fees, locale: locale), reversalOfActivityId: correcting?.activity.reversalOfActivityId)
            let value = try await model.controller.householdResponse(FinancialActivityPreview.self, path: model.path(household.id, "/activities" + (correcting.map { "/" + $0.id.uuidString } ?? "") + "/preview"), method: "POST", body: JSONEncoder().encode(HouseholdFinancialCommand(membershipId: household.membershipId, expectedVersion: household.version, activity: command)), expectedIdentity: identity)
            guard current else { return }; preview = value
        } catch {
            guard current else { return }
            if !(await model.resolveAccessFailure(error, householdId: household.id)), current { errorKey = "household.reviewError" }
        }
    }
    func confirm() async {
        guard let model, current, let preview, preview.ready, var command = preview.reviewedRequest else { return }
        command.previewToken = preview.previewToken
        await model.confirmActivity(command, activityId: correcting?.id, membership: household.membershipId, version: household.version)
    }
}

struct HouseholdActivityEditorView: View {
    @ObservedObject var model: HouseholdActivityEditor
    @Environment(\.locale) private var locale
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focused: Bool
    var body: some View {
        NavigationStack {
            Form {
                if model.options == nil { ProgressView("accounts.loading") }
                else {
                    Section {
                        if model.correcting == nil {
                            Picker("household.activity", selection: $model.kind) { ForEach(model.kinds, id: \.self) { Text(LocalizedStringKey("loop.kind." + $0.rawValue)).tag($0) } }.accessibilityIdentifier("household.activity.kind")
                        }
                        if model.kind.isPaired {
                            accountPicker("household.sourceAccount", selection: $model.sourceId, types: model.options?.eligibility[model.kind.rawValue])
                            accountPicker("household.destinationAccount", selection: $model.destinationId, types: model.options?.destinationEligibility[model.kind.rawValue])
                        } else { accountPicker("household.account", selection: $model.accountId, types: model.options?.eligibility[model.kind.rawValue]) }
                        TextField("household.amount", text: $model.amount).keyboardType(.decimalPad).focused($focused).accessibilityIdentifier("household.activity.amount")
                        if model.kind == .debtPayment || model.kind == .paymentReversal && model.correcting?.activity.principalMinor != nil {
                            TextField("household.principal", text: $model.principal).keyboardType(.decimalPad).focused($focused)
                            TextField("household.interest", text: $model.interest).keyboardType(.decimalPad).focused($focused)
                            TextField("household.fees", text: $model.fees).keyboardType(.decimalPad).focused($focused)
                        }
                        DatePicker("household.date", selection: $model.date, displayedComponents: [.date])
                        if model.kind == .expense || model.kind == .refund {
                            Picker("household.category", selection: $model.category) {
                                Text("household.choose").tag(String?.none)
                                ForEach(model.options?.categories ?? [], id: \.self) { Text(LocalizedStringKey("loop.category." + $0)).tag(Optional($0)) }
                            }
                        }
                        if model.kind == .income {
                            Picker("household.source", selection: $model.incomeSource) {
                                Text("household.choose").tag(String?.none)
                                ForEach(model.options?.sources ?? [], id: \.self) { Text(LocalizedStringKey("loop.source." + $0)).tag(Optional($0)) }
                            }
                        }
                        if model.kind == .refund {
                            Picker("household.purchase", selection: $model.purchase) {
                                Text("household.unlinked").tag(UUID?.none)
                                ForEach(model.snapshot.activities.filter { $0.activity.kind == .expense && $0.canEdit }) { item in Text(item.activity.note ?? item.activity.amount ?? "").tag(Optional(item.id)) }
                            }
                        }
                        TextField("household.note", text: $model.note).focused($focused).accessibilityIdentifier("household.activity.note")
                        if model.correcting != nil { TextField("household.reason", text: $model.reason).focused($focused).accessibilityIdentifier("household.activity.reason") }
                    }.disabled(model.busy)
                    if let preview = model.preview {
                        Section("household.review") {
                            ForEach(preview.affectedAccounts) { effect in
                                Text(effect.currency + " " + (effect.before.amount ?? "?") + " → " + (effect.after?.amount ?? "?"))
                                ForEach(effect.observations, id: \.observationId) { observation in
                                    Text(observation.asOf)
                                    Button("household.included") { model.answer(effect.accountId, observation.observationId, true) }
                                    Button("household.notIncluded") { model.answer(effect.accountId, observation.observationId, false) }
                                }
                            }
                        }
                    }
                    if let error = model.errorKey { Text(LocalizedStringKey(error)).accessibilityIdentifier("household.activity.error") }
                    if model.preview?.ready == true {
                        Button("household.confirmActivity") { focused = false; Task { await model.confirm() } }.accessibilityIdentifier("household.activity.confirm")
                    } else {
                        Button("household.review") { focused = false; Task { await model.review(locale) } }.accessibilityIdentifier("household.activity.review").disabled(model.amount.isEmpty || model.busy)
                    }
                }
            }
            .navigationTitle(model.correcting == nil ? "household.recordActivity" : "household.correct")
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                CuadraoCancelToolbar(title: "accounts.cancel") { dismiss() }
            }.task { await model.load() }
        }
    }
    private func accountPicker(_ label: LocalizedStringKey, selection: Binding<UUID?>, types: [String]?) -> some View {
        Picker(label, selection: selection) {
            Text("household.choose").tag(UUID?.none)
            ForEach(model.choices.filter { types?.contains($0.type) == true }) { account in Text((account.nickname ?? account.type) + " · " + account.currency).tag(Optional(account.id)) }
        }
    }
}

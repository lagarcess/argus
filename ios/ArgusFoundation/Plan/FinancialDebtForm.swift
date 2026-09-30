import SwiftUI
import ArgusSession

@MainActor
final class FinancialDebtDraft: ObservableObject, Identifiable {
    let id = UUID()
    let existing: FinancialDebt?
    let debtAccountID: UUID
    let currency: String
    @Published var name: String
    @Published var sourceID: UUID?
    @Published var amount = ""
    @Published var start: Date
    @Published var cadence = FinancialPlanSchedule.Cadence.monthly
    @Published var firstDay: Int
    @Published var secondDay = 31
    @Published var hasEnd = false
    @Published var end: Date
    @Published var effective: Date
    @Published var estimate = false
    @Published var rate = ""
    @Published var fees = ""
    @Published var periodStart: Date
    init(account: FinancialAccount, start: String) {
        existing = nil; debtAccountID = account.id; currency = account.currency
        name = account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")
        let date = PlanPresentation.date(start)
        self.start = date; end = date; effective = date; periodStart = date
        firstDay = PlanPresentation.monthDay(start)
    }
    init(debt: FinancialDebt) {
        existing = debt; debtAccountID = debt.debtAccountId; currency = debt.currency; name = debt.name
        sourceID = debt.sourceAccountId; amount = AccountPresentation.amount(debt.amount, locale: .current)
        start = PlanPresentation.date(debt.schedule.startDate); cadence = debt.schedule.cadence
        firstDay = debt.schedule.monthDays.first ?? PlanPresentation.monthDay(debt.schedule.startDate)
        secondDay = debt.schedule.monthDays.last ?? 31
        hasEnd = debt.schedule.endDate != nil; end = PlanPresentation.date(debt.schedule.endDate ?? debt.earliestEffectiveDate)
        effective = PlanPresentation.date(debt.earliestEffectiveDate)
        estimate = debt.assumptions != nil
        rate = debt.assumptions.map { AccountPresentation.amount($0.annualRatePercent, locale: .current) } ?? ""
        fees = debt.assumptions.map { AccountPresentation.amount($0.recurringFees, locale: .current) } ?? ""
        periodStart = PlanPresentation.date(debt.assumptions?.firstPeriodStart ?? debt.earliestEffectiveDate)
    }
    var ready: Bool { !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && name.count <= 100 && sourceID != nil && !amount.isEmpty && (!estimate || (!rate.isEmpty && !fees.isEmpty)) }
    func command(locale: Locale) throws -> FinancialDebtCommand {
        guard ready, let exact = try AccountEntry.amount(amount, locale: locale) else { throw AccountEntry.Failure.amount }
        let old = existing?.schedule
        let unchangedAnchor = old?.cadence == .monthly && old?.monthDays.isEmpty == true && old?.startDate == PlanPresentation.day(start) && firstDay == PlanPresentation.monthDay(PlanPresentation.day(start))
        let days = cadence == .twiceMonthly ? [firstDay, secondDay] : cadence == .monthly && !unchangedAnchor ? [firstDay] : []
        let schedule = FinancialPlanSchedule(cadence: cadence, startDate: PlanPresentation.day(start), endDate: hasEnd ? PlanPresentation.day(end) : nil, monthDays: days)
        let sourceChanged = existing.map { $0.sourceAccountId != sourceID } ?? true
        let amountChanged = existing.map { $0.amount != exact } ?? true
        let scheduleChanged = existing.map { $0.schedule != schedule } ?? true
        let changed = sourceChanged || amountChanged || scheduleChanged
        let assumptions: FinancialDebtAssumptions?
        if estimate, let rate = try AccountEntry.amount(rate, locale: locale), let fees = try AccountEntry.amount(fees, locale: locale) {
            assumptions = .init(annualRatePercent: rate, recurringFees: fees, firstPeriodStart: PlanPresentation.day(periodStart))
        } else { assumptions = nil }
        return .init(name: name, debtAccountId: existing == nil ? debtAccountID : nil, sourceAccountId: sourceChanged ? sourceID : nil,
                     amount: amountChanged ? exact : nil, schedule: scheduleChanged ? schedule : nil, assumptions: assumptions,
                     expectedVersion: existing?.version, effectiveDate: existing != nil && changed ? PlanPresentation.day(effective) : nil)
    }
}

struct FinancialDebtForm: View {
    @ObservedObject var model: FinancialDebtModel
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject var draft: FinancialDebtDraft
    @Environment(\.locale) private var locale
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focused: Bool
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Group {
                        field("debt.name", "debt.name", $draft.name)
                        Picker("debt.source", selection: $draft.sourceID) {
                            Text("plan.account.unassigned").tag(nil as UUID?)
                            ForEach((loop.plan.projection?.accounts ?? []).filter { !$0.archived && $0.currency == draft.currency && ["cash", "checking", "savings"].contains($0.type) }) { account in
                                Text(loop.accountName(account.id)).tag(Optional(account.id))
                            }
                        }.accessibilityIdentifier("debt.source")
                        field("debt.amount", "debt.amount", $draft.amount).keyboardType(.decimalPad)
                        Text(verbatim: draft.currency).foregroundStyle(ArgusStyle.secondary)
                        DatePicker("plan.date", selection: $draft.start, displayedComponents: .date).accessibilityIdentifier("debt.scheduleDate")
                        Picker("plan.repeat", selection: $draft.cadence) {
                            ForEach(FinancialPlanSchedule.Cadence.allCases, id: \.self) { Text(LocalizedStringKey("plan.repeat." + $0.rawValue)).tag($0) }
                        }.accessibilityIdentifier("debt.recurrence")
                        if draft.cadence == .monthly || draft.cadence == .twiceMonthly {
                            monthDay("plan.monthDay", $draft.firstDay)
                            if draft.cadence == .twiceMonthly { monthDay("plan.secondMonthDay", $draft.secondDay) }
                        }
                        if draft.cadence != .once {
                            Toggle("plan.hasEnd", isOn: $draft.hasEnd)
                            if draft.hasEnd { DatePicker("plan.endDate", selection: $draft.end, displayedComponents: .date) }
                        }
                        if let existing = draft.existing {
                            DatePicker("plan.effectiveDate", selection: $draft.effective, in: PlanPresentation.date(existing.earliestEffectiveDate)..., displayedComponents: .date)
                            Text("plan.cutover.hint").font(ArgusStyle.body(12, relativeTo: .caption))
                        }
                        Text("debt.plan.disclosure").foregroundStyle(ArgusStyle.secondary)
                        DisclosureGroup("debt.estimate") {
                            VStack(alignment: .leading, spacing: 16) {
                                Toggle("debt.estimate.enable", isOn: $draft.estimate).accessibilityIdentifier("debt.estimate.enable")
                                if draft.estimate {
                                    Text("debt.estimate.assumptions").foregroundStyle(ArgusStyle.secondary)
                                    field("debt.rate", "debt.rate", $draft.rate).keyboardType(.decimalPad)
                                    field("debt.fees", "debt.fees", $draft.fees).keyboardType(.decimalPad)
                                    DatePicker("debt.periodStart", selection: $draft.periodStart, displayedComponents: .date)
                                    Text("debt.estimate.boundary").font(ArgusStyle.body(12, relativeTo: .caption))
                                }
                            }.padding(.top, 12)
                        }
                    }.disabled(model.saving || loop.pendingConfirmation != nil)
                    if let key = model.errorKey { Text(LocalizedStringKey(key)).accessibilityIdentifier("debt.error") }
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    else { Button("debt.save") { focused = false; Task { await model.save(locale: locale) } }.buttonStyle(PillButtonStyle()).disabled(!draft.ready || model.saving).accessibilityIdentifier("debt.save") }
                }.padding(24)
            }.background(ArgusStyle.background).scrollDismissesKeyboard(.interactively).environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                .navigationTitle(draft.existing == nil ? "debt.add" : "debt.edit").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("accounts.cancel") { dismiss() }.disabled(model.saving) }
                    ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("accounts.keyboard.done") { focused = false } }
                }.interactiveDismissDisabled(model.saving)
        }
    }
    private func field(_ title: LocalizedStringKey, _ id: String, _ text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(title); TextField(title, text: text).focused($focused).padding(14).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line)).accessibilityIdentifier(id) }
    }
    private func monthDay(_ title: LocalizedStringKey, _ selection: Binding<Int>) -> some View {
        Picker(title, selection: selection) { ForEach(1...31, id: \.self) { day in if day == 31 { Text("plan.lastDay").tag(day) } else { Text(verbatim: String(day)).tag(day) } } }
    }
}

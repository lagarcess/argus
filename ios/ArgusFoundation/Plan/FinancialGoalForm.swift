import SwiftUI
import ArgusSession

@MainActor
final class FinancialGoalDraft: ObservableObject, Identifiable {
    let id = UUID()
    let existing: FinancialGoal?
    @Published var name = ""
    @Published var target = ""
    @Published var currency: String
    @Published var hasTargetDate = false
    @Published var targetDate: Date
    @Published var destinationID: UUID?
    @Published var hasPlan = false
    @Published var sourceID: UUID?
    @Published var amount = ""
    @Published var start: Date
    @Published var cadence = FinancialPlanSchedule.Cadence.monthly
    @Published var firstDay = 15
    @Published var secondDay = 31
    @Published var hasEnd = false
    @Published var end: Date
    @Published var effective: Date
    init(start: String, currency: String) {
        existing = nil; self.currency = currency
        let date = PlanPresentation.date(start); self.start = date; targetDate = date; end = date; effective = date
        firstDay = PlanPresentation.monthDay(start)
    }
    init(goal: FinancialGoal) {
        existing = goal; name = goal.name; currency = goal.currency; target = AccountPresentation.amount(goal.target, locale: .current)
        hasTargetDate = goal.targetDate != nil; targetDate = PlanPresentation.date(goal.targetDate ?? goal.earliestEffectiveDate)
        destinationID = goal.destinationAccountId; hasPlan = goal.contributionPlan != nil
        sourceID = goal.contributionPlan?.sourceAccountId
        amount = goal.contributionPlan.map { AccountPresentation.amount($0.amount, locale: .current) } ?? ""
        let schedule = goal.contributionPlan?.schedule
        start = PlanPresentation.date(schedule?.startDate ?? goal.earliestEffectiveDate)
        cadence = schedule?.cadence ?? .monthly
        firstDay = schedule?.monthDays.first ?? PlanPresentation.monthDay(schedule?.startDate ?? goal.earliestEffectiveDate)
        secondDay = schedule?.monthDays.last ?? 31
        hasEnd = schedule?.endDate != nil; end = PlanPresentation.date(schedule?.endDate ?? goal.earliestEffectiveDate)
        effective = PlanPresentation.date(goal.earliestEffectiveDate)
    }
    var ready: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && name.count <= 100 && !target.isEmpty &&
        (!hasPlan || (destinationID != nil && sourceID != nil && destinationID != sourceID && !amount.isEmpty))
    }
    func command(locale: Locale) throws -> FinancialGoalCommand {
        guard ready, let exact = try AccountEntry.amount(target, locale: locale) else { throw AccountEntry.Failure.amount }
        let plan: FinancialGoalPlan?
        if hasPlan, let sourceID, let amount = try AccountEntry.amount(amount, locale: locale) {
            let previous = existing?.contributionPlan?.schedule
            let unchangedAnchor = previous?.cadence == .monthly && previous?.monthDays.isEmpty == true &&
                previous?.startDate == PlanPresentation.day(start) && firstDay == PlanPresentation.monthDay(PlanPresentation.day(start))
            let monthDays = cadence == .twiceMonthly ? [firstDay, secondDay] : cadence == .monthly && !unchangedAnchor ? [firstDay] : []
            plan = .init(sourceAccountId: sourceID, amount: amount, schedule: .init(cadence: cadence,
                startDate: PlanPresentation.day(start), endDate: hasEnd ? PlanPresentation.day(end) : nil, monthDays: monthDays))
        } else { plan = nil }
        let changed = existing.map { $0.destinationAccountId != destinationID || $0.contributionPlan != plan } ?? true
        return .init(name: name, currency: existing == nil ? currency : nil, target: exact,
            targetDate: hasTargetDate ? PlanPresentation.day(targetDate) : nil, destinationAccountId: destinationID,
            contributionPlan: plan, includesSetup: changed, expectedVersion: existing?.version,
            effectiveDate: existing != nil && changed ? PlanPresentation.day(effective) : nil)
    }
}

struct FinancialGoalForm: View {
    @ObservedObject var model: FinancialGoalModel
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject var draft: FinancialGoalDraft
    @Environment(\.locale) private var locale
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focused: Bool
    private var accounts: [FinancialAccount] {
        (loop.plan.projection?.accounts ?? []).filter { $0.currency == draft.currency && ["cash", "checking", "savings"].contains($0.type) }
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Group {
                        field("goal.name", id: "goal.name", text: $draft.name)
                        Picker("accounts.currency", selection: $draft.currency) {
                            ForEach(Array(Set((loop.plan.projection?.accounts.map(\.currency) ?? []) + [draft.currency, "DOP", "USD"])).sorted(), id: \.self) { Text(verbatim: $0).tag($0) }
                        }.disabled(draft.existing != nil).accessibilityIdentifier("goal.currency")
                        field("goal.target", id: "goal.target", text: $draft.target).keyboardType(.decimalPad)
                        Toggle("goal.hasDate", isOn: $draft.hasTargetDate).accessibilityIdentifier("goal.hasDate")
                        if draft.hasTargetDate { DatePicker("goal.targetDate", selection: $draft.targetDate, displayedComponents: .date).accessibilityIdentifier("goal.targetDate") }
                        accountPicker("goal.destination", id: "goal.destination", selection: $draft.destinationID)
                        Toggle("goal.plan", isOn: $draft.hasPlan).accessibilityIdentifier("goal.plan")
                        if draft.hasPlan {
                            accountPicker("goal.source", id: "goal.source", selection: $draft.sourceID)
                            field("goal.contributionAmount", id: "goal.contributionAmount", text: $draft.amount).keyboardType(.decimalPad)
                            DatePicker("plan.date", selection: $draft.start, displayedComponents: .date).accessibilityIdentifier("goal.scheduleDate")
                            Picker("plan.repeat", selection: $draft.cadence) {
                                ForEach(FinancialPlanSchedule.Cadence.allCases, id: \.self) { Text(LocalizedStringKey("plan.repeat." + $0.rawValue)).tag($0) }
                            }.accessibilityIdentifier("goal.recurrence")
                            if draft.cadence == .monthly || draft.cadence == .twiceMonthly {
                                monthDay("plan.monthDay", selection: $draft.firstDay)
                                if draft.cadence == .twiceMonthly { monthDay("plan.secondMonthDay", selection: $draft.secondDay) }
                            }
                            if draft.cadence != .once {
                                Toggle("plan.hasEnd", isOn: $draft.hasEnd)
                                if draft.hasEnd { DatePicker("plan.endDate", selection: $draft.end, displayedComponents: .date) }
                            }
                        }
                        if let existing = draft.existing {
                            DatePicker("plan.effectiveDate", selection: $draft.effective, in: PlanPresentation.date(existing.earliestEffectiveDate)..., displayedComponents: .date)
                            Text("plan.cutover.hint").font(ArgusStyle.body(12, relativeTo: .caption))
                        }
                        Text("goal.plan.disclosure").foregroundStyle(ArgusStyle.secondary)
                        Text(verbatim: loop.plan.projection?.selection.timeZone ?? "").font(ArgusStyle.body(12, relativeTo: .caption))
                    }.disabled(model.saving || loop.pendingConfirmation != nil)
                    if let error = model.errorKey { Text(LocalizedStringKey(error)).accessibilityIdentifier("goal.error") }
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    else {
                        Button("goal.save") { focused = false; Task { await model.save(locale: locale) } }
                            .buttonStyle(PillButtonStyle()).disabled(!draft.ready || model.saving).accessibilityIdentifier("goal.save")
                    }
                }.padding(24).font(ArgusStyle.body())
            }.background(ArgusStyle.background).scrollDismissesKeyboard(.interactively)
                .environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                .navigationTitle(draft.existing == nil ? "goal.add" : "goal.edit").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("accounts.cancel") { dismiss() }.disabled(model.saving) }
                    ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("accounts.keyboard.done") { focused = false } }
                }.interactiveDismissDisabled(model.saving)
                .onChange(of: draft.currency) { _, _ in draft.destinationID = nil; draft.sourceID = nil }
        }
    }
    private func field(_ title: LocalizedStringKey, id: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
            TextField(title, text: text).focused($focused).padding(14).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line)).accessibilityIdentifier(id)
        }
    }
    private func accountPicker(_ title: LocalizedStringKey, id: String, selection: Binding<UUID?>) -> some View {
        Picker(title, selection: selection) {
            Text("plan.account.unassigned").tag(nil as UUID?)
            ForEach(accounts) { Text(loop.accountName($0.id)).tag(Optional($0.id)) }
        }.accessibilityIdentifier(id)
    }
    private func monthDay(_ title: LocalizedStringKey, selection: Binding<Int>) -> some View {
        Picker(title, selection: selection) {
            ForEach(1...31, id: \.self) { day in
                if day == 31 { Text("plan.lastDay").tag(day) } else { Text(verbatim: String(day)).tag(day) }
            }
        }
    }
}

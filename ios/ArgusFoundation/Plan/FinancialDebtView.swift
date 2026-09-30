import SwiftUI
import ArgusSession

struct FinancialDebtList: View {
    @ObservedObject var plan: FinancialPlanModel
    @ObservedObject var model: FinancialDebtModel
    let origin: FinancialDebtNavigation.Origin
    var compact = false
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("plan.debts").font(ArgusStyle.display(23))
            let items = plan.projection?.debts ?? []
            if items.filter({ !$0.debt.archived }).isEmpty { Text("debt.empty").foregroundStyle(ArgusStyle.secondary) }
            ForEach(items.filter { !$0.debt.archived }) { progress in row(progress) }
            if !compact {
                Button("debt.add") { model.create() }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("debt.add")
                if items.contains(where: { $0.debt.archived }) {
                    DisclosureGroup("debt.archived") { ForEach(items.filter { $0.debt.archived }) { progress in row(progress) } }
                }
            }
        }
    }
    private func row(_ progress: FinancialDebtProgress) -> some View {
        Button { Task { await model.open(progress.id, origin: origin) } } label: {
            VStack(alignment: .leading, spacing: 10) {
                HStack { Text(verbatim: progress.debt.name); Spacer(); Image(systemName: "chevron.right") }
                FinancialDebtSummary(progress: progress)
            }.padding(.vertical, 14).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("debt.row." + origin.rawValue + "." + progress.id.uuidString)
    }
}

struct FinancialDebtSummary: View {
    let progress: FinancialDebtProgress
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(progress.balance.creditMinor != nil && progress.balance.creditMinor != 0 ? "debt.credit" : "debt.recorded")
            Text(verbatim: money(progress.balance.creditMinor != nil && progress.balance.creditMinor != 0 ? progress.balance.creditMinor.map(String.init) : progress.balance.amountMinor.map(String.init)))
                .font(ArgusStyle.display(28)).monospacedDigit().accessibilityIdentifier("debt.recorded")
            Text(LocalizedStringKey("debt.state." + progress.state)).foregroundStyle(progress.state == "needs_review" ? ArgusStyle.negative : ArgusStyle.secondary).accessibilityIdentifier("debt.state")
        }
    }
    private func money(_ minor: String?) -> String { minor.map { PlanPresentation.money($0, currency: progress.debt.currency, digits: progress.debt.currencyFractionDigits, locale: locale) } ?? NSLocalizedString("accounts.unknown", comment: "") }
}

struct FinancialDebtFunding: View {
    let pool: FinancialGoalPool
    let digits: Int
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            DisclosureGroup("debt.funding") {
                VStack(alignment: .leading, spacing: 10) {
                    PlanValueRow(title: "debt.funding.recorded", value: money(pool.backingMinor))
                    PlanValueRow(title: "debt.funding.assigned", value: money(pool.assignedMinor))
                    PlanValueRow(title: "debt.funding.available", value: money(pool.availableMinor)).accessibilityIdentifier("debt.funding.available")
                    if pool.state == "shortfall" {
                        PlanValueRow(title: "goal.shortfall", value: money(pool.shortfallMinor))
                        Text(pool.affectedGoalNames.joined(separator: " · "))
                    }
                }.padding(.top, 12)
            }
            if pool.state == "shortfall" {
                Text("goal.reason.pool_shortfall").foregroundStyle(ArgusStyle.negative).accessibilityIdentifier("debt.funding.shortfall")
            }
        }
    }
    private func money(_ value: String?) -> String { value.map { PlanPresentation.money($0, currency: pool.currency, digits: digits, locale: locale) } ?? NSLocalizedString("accounts.unknown", comment: "") }
}

struct FinancialDebtPresenter: View {
    @ObservedObject var model: FinancialDebtModel
    @ObservedObject var loop: FinancialLoopModel
    @Binding var destination: AppDestination
    let search: FinancialSearchModel?
    var body: some View {
        ZStack {
            if model.navigation != nil {
                Color.black.opacity(0.25).ignoresSafeArea()
                FinancialDebtDetail(model: model, loop: loop) {
                    switch model.navigation?.origin { case .home: destination = .home; case .plan: destination = .plan; loop.plan.section = .debts; case .search: destination = .search; case .account: destination = .accounts; case nil: break }
                    model.close(); Task { await search?.refresh() }
                }.background(ArgusStyle.background).clipShape(RoundedRectangle(cornerRadius: 24)).padding(12).accessibilityElement(children: .contain).accessibilityIdentifier("debt.detail")
            } else { Color.clear.allowsHitTesting(false) }
        }
        .sheet(item: $model.draft, onDismiss: { Task { await search?.refresh() } }) { draft in FinancialDebtForm(model: model, loop: loop, draft: draft) }
        .sheet(isPresented: $model.choosingAccount, onDismiss: model.accountChooserDismissed) {
            NavigationStack {
                List((loop.plan.projection?.accounts ?? []).filter { account in !account.archived && ["credit_card", "other_debt"].contains(account.type) && !(loop.plan.projection?.debts ?? []).contains(where: { !$0.debt.archived && $0.debt.debtAccountId == account.id }) }) { account in
                    Button(loop.accountName(account.id)) { model.chooseAccount(account) }.accessibilityIdentifier("debt.account." + account.id.uuidString)
                }.navigationTitle("debt.chooseAccount").toolbar { ToolbarItem(placement: .cancellationAction) { Button("accounts.cancel") { model.choosingAccount = false } } }
            }
        }
        .sheet(isPresented: $model.linking) { FinancialDebtLinkView(model: model, loop: loop) }
    }
}

struct FinancialDebtDetail: View {
    @ObservedObject var model: FinancialDebtModel
    @ObservedObject var loop: FinancialLoopModel
    let close: () -> Void
    @State private var archiving = false
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                if model.navigation?.activityID != nil { Button { model.activity(nil); Task { await model.refreshIfOpen() } } label: { Label("debt.back", systemImage: "chevron.left") }.accessibilityIdentifier("debt.activity.back") }
                else if let detail = model.detail { Text(verbatim: detail.debt.name).font(ArgusStyle.display(23)) }
                Spacer(); Button(action: close) { Image(systemName: "xmark").frame(width: 48, height: 48) }.accessibilityLabel("action.close").accessibilityIdentifier("debt.close")
            }.padding(.horizontal, 20)
            ScrollViewReader { reader in
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        if let id = model.navigation?.activityID { FinancialActivityDetailView(loop: loop, activityID: id) { loop.correct($0) } }
                        else if let progress = model.detail {
                            FinancialDebtSummary(progress: progress)
                            PlanValueRow(title: "debt.source", value: loop.accountName(progress.debt.sourceAccountId))
                            PlanValueRow(title: "debt.amount", value: money(String(progress.debt.amountMinor), progress))
                            Text(LocalizedStringKey("plan.repeat." + progress.debt.schedule.cadence.rawValue))
                            Text("debt.plan.disclosure").foregroundStyle(ArgusStyle.secondary)
                            if let pool = progress.fundingPool { FinancialDebtFunding(pool: pool, digits: progress.debt.currencyFractionDigits) }
                            if !progress.debt.archived {
                                occurrencePicker(progress)
                                Button("debt.record") { model.record() }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("debt.record")
                                Button("debt.extra") { model.record(extra: true) }.frame(minHeight: 44).accessibilityIdentifier("debt.extra")
                                Button("debt.link") { Task { await model.loadCandidates() } }.frame(minHeight: 44).accessibilityIdentifier("debt.link")
                            }
                            DisclosureGroup("debt.estimate") { payoff(progress).padding(.top, 12) }
                            Text("debt.payments").font(ArgusStyle.display(21))
                            if progress.payments.isEmpty { Text("debt.noPayments").foregroundStyle(ArgusStyle.secondary) }
                            ForEach(progress.payments) { payment in
                                Button { model.activity(payment.activityId) } label: {
                                    VStack(alignment: .leading, spacing: 8) {
                                        HStack { Text(payment.activity?.note ?? NSLocalizedString("debt.payment", comment: "")); Spacer(); Text(verbatim: money(payment.netPaidMinor.map(String.init), progress)); Image(systemName: "chevron.right") }
                                        Text(LocalizedStringKey("debt.payment." + payment.status)).foregroundStyle(ArgusStyle.secondary)
                                    }.frame(minHeight: 48)
                                }.buttonStyle(.plain).id(payment.activityId).accessibilityIdentifier("debt.activity." + payment.activityId.uuidString)
                            }
                            if progress.debt.archived { Button("debt.restore") { Task { await model.archive(false) } }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("debt.restore") }
                            else {
                                Button("debt.edit") { model.edit() }.buttonStyle(PillButtonStyle(primary: false)).accessibilityIdentifier("debt.edit")
                                Button("debt.archive") { archiving = true }.frame(minHeight: 48).accessibilityIdentifier("debt.archive")
                            }
                        }
                        if model.loading { ProgressView("accounts.loading") }
                        if let key = model.errorKey { Text(LocalizedStringKey(key)).accessibilityIdentifier("debt.error"); Button("accounts.retry") { Task { await model.refreshIfOpen() } } }
                        if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    }.padding(24).disabled(model.saving)
                }.task(id: model.detail?.payments.map(\.activityId)) { if let anchor = model.navigation?.anchor { await Task.yield(); reader.scrollTo(anchor, anchor: .top) } }
            }
        }.confirmationDialog("debt.archive", isPresented: $archiving, titleVisibility: .visible) {
            Button("debt.archive") { Task { await model.archive(true) } }.accessibilityIdentifier("debt.archive.confirm")
            Button("accounts.cancel", role: .cancel) { }
        } message: { Text("debt.archive.disclosure") }
    }
    private func occurrencePicker(_ progress: FinancialDebtProgress) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker("debt.occurrence", selection: Binding(get: { model.occurrenceID }, set: { model.chooseOccurrence($0) })) {
                Text("debt.extra").tag(nil as String?)
                ForEach(progress.occurrences) { occurrence in Text(PlanPresentation.dateLabel(occurrence.dueDate, locale: locale)).tag(Optional(occurrence.id)) }
            }.accessibilityIdentifier("debt.occurrence")
            if let occurrence = progress.occurrences.first(where: { $0.id == model.occurrenceID }) {
                PlanValueRow(title: "debt.paid", value: money(occurrence.paidMinor.map(String.init), progress))
                PlanValueRow(title: "debt.remaining", value: money(occurrence.remainingMinor.map(String.init), progress)).accessibilityIdentifier("debt.remaining")
                Text(LocalizedStringKey("plan.status." + occurrence.status.rawValue))
                if occurrence.overdue { Text("plan.overdue").foregroundStyle(ArgusStyle.secondary) }
            }
        }
    }
    private func payoff(_ progress: FinancialDebtProgress) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if let date = progress.payoff.payoffDate {
                Text("debt.estimate.conditional"); Text(PlanPresentation.dateLabel(date, locale: locale)).accessibilityIdentifier("debt.payoff")
                if let count = progress.payoff.payments { PlanValueRow(title: "debt.estimate.payments", value: String(count)) }
                PlanValueRow(title: "debt.interest", value: money(progress.payoff.totalInterestMinor, progress))
                PlanValueRow(title: "debt.fees", value: money(progress.payoff.totalFeesMinor, progress))
            } else { Text(LocalizedStringKey("debt.payoff." + (progress.payoff.reason ?? "terms_missing"))) }
            if let assumptions = progress.payoff.assumptions {
                PlanValueRow(title: "debt.rate", value: assumptions.annualRatePercent + "%")
                PlanValueRow(title: "debt.fees", value: progress.debt.currency + " " + AccountPresentation.amount(assumptions.recurringFees, locale: locale))
            }
            Text("debt.estimate.assumptions").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
        }
    }
    private func money(_ value: String?, _ progress: FinancialDebtProgress) -> String { value.map { PlanPresentation.money($0, currency: progress.debt.currency, digits: progress.debt.currencyFractionDigits, locale: locale) } ?? NSLocalizedString("accounts.unknown", comment: "") }
}

struct FinancialDebtLinkView: View {
    @ObservedObject var model: FinancialDebtModel
    @ObservedObject var loop: FinancialLoopModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("debt.link.disclosure").foregroundStyle(ArgusStyle.secondary)
                    if model.loading { ProgressView("accounts.loading") }
                    if model.candidates.isEmpty && !model.loading { Text("debt.link.empty").accessibilityIdentifier("debt.link.empty") }
                    ForEach(model.candidates) { entry in
                        Button { Task { await model.link(entry) } } label: {
                            HStack { Text(entry.note ?? NSLocalizedString("debt.payment", comment: "")); Spacer(); Text(verbatim: entry.currency + " " + AccountPresentation.amount(entry.amount, locale: locale)) }.frame(minHeight: 48)
                        }.buttonStyle(.plain).disabled(model.saving || loop.pendingConfirmation != nil).accessibilityIdentifier("debt.candidate." + entry.activityId.uuidString)
                    }
                    if let key = model.errorKey { Text(LocalizedStringKey(key)).accessibilityIdentifier("debt.error") }
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                }.padding(24)
            }.navigationTitle("debt.link").toolbar { ToolbarItem(placement: .cancellationAction) { Button("accounts.cancel") { dismiss() }.disabled(model.saving).accessibilityIdentifier("debt.action.cancel") } }
        }
    }
}

private struct FinancialDebtOcclusion: ViewModifier {
    @ObservedObject var model: FinancialDebtModel
    func body(content: Content) -> some View { content.accessibilityHidden(model.navigation != nil).allowsHitTesting(model.navigation == nil) }
}
extension View {
    @ViewBuilder func financialDebtBackground(_ model: FinancialDebtModel?) -> some View { if let model { modifier(FinancialDebtOcclusion(model: model)) } else { self } }
}

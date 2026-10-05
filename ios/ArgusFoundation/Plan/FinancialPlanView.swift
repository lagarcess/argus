import SwiftUI
import ArgusSession

struct FinancialPlanDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let showProfile: () -> Void
    var audience: Binding<Bool>? = nil
    var body: some View {
        if auth.state == .authenticated, let loop = auth.financialLoop {
            FinancialPlanView(model: loop.plan, loop: loop, audience: audience)
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    PersonalContext()
                    Text("plan.overview.empty").font(ArgusStyle.display())
                    Text("accounts.gate.body").foregroundStyle(ArgusStyle.secondary)
                    Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                }.padding(24)
            }
        }
    }
}

struct FinancialPlanView: View {
    @ObservedObject var model: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    var audience: Binding<Bool>? = nil
    @State private var selectingAccounts = false
    @State private var expanded = false
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                CuadraoPlanHeader(spanish: spanish, createTitle: NSLocalizedString(createKey, comment: ""),
                    canCreate: model.projection != nil && loop.pendingConfirmation == nil && !model.saving, create: create)
                if let audience { CuadraoPlanAudiencePicker(spanish: spanish, together: audience) }
                if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                if model.loading { ProgressView("accounts.loading") }
                if let error = model.errorKey {
                    Text(LocalizedStringKey(error)).foregroundStyle(.secondary)
                    Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44)
                }
                if model.section == .overview {
                    if let projection = model.projection { overview(projection) }
                } else {
                    sections
                    if model.section == .goals {
                        FinancialGoalList(plan: model, model: loop.goals, origin: .plan)
                    } else if model.section == .debts {
                        FinancialDebtList(plan: model, model: loop.debts, origin: .plan)
                    } else if model.section == .budgets {
                        FinancialBudgetList(plan: model, model: loop.budgets, origin: .plan)
                    }
                }
            }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, 24)
        }
        .scrollIndicators(.hidden).background(WelcomePalette.background)
        .foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine).cuadraoSoftScrollEdges()
        .task { if model.projection == nil { await model.refresh() } }
        .refreshable { await loop.refresh() }
        .sheet(isPresented: $selectingAccounts) {
            if let projection = model.projection { FinancialPlanSelectionView(model: model, loop: loop, projection: projection) }
        }
    }

    private var sections: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 24) {
                ForEach(PlanSection.allCases, id: \.self) { item in
                    Button { model.section = item } label: {
                        Text(item.title).font(CuadraoTypography.supporting).frame(minWidth: 44, minHeight: 48)
                            .foregroundStyle(model.section == item ? WelcomePalette.ink : .secondary)
                            .overlay(alignment: .bottom) {
                                Rectangle().fill(model.section == item ? WelcomePalette.pine : .clear).frame(height: 1)
                            }.contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("plan." + item.rawValue)
                        .accessibilityAddTraits(model.section == item ? .isSelected : [])
                }
            }
        }
    }

    private func overview(_ projection: FinancialPlanProjection) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            FinancialPlanForecast(projection: projection)
            DatePicker("plan.until.label", selection: Binding(get: { PlanPresentation.date(projection.endDate) },
                set: { date in Task { await model.refresh(until: PlanPresentation.day(date)) } }),
                in: PlanPresentation.date(projection.startDate)...PlanPresentation.date(projection.startDate).addingTimeInterval(366 * 86400),
                displayedComponents: .date)
                .environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                .font(CuadraoTypography.supporting).accessibilityIdentifier("plan.until")
            Button { selectingAccounts = true } label: {
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text("plan.includedAccounts"); Spacer(); Image(systemName: "chevron.right").font(.caption2) }
                    Text(includedNames(projection)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }.font(CuadraoTypography.supporting).frame(minHeight: 48).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("plan.accounts").disabled(loop.pendingConfirmation != nil)
            Text(projection.selection.timeZone).font(CuadraoTypography.caption).foregroundStyle(.secondary)
            if !projection.hasExpectations { Text("plan.empty").font(CuadraoTypography.supporting).foregroundStyle(.secondary) }
            FinancialPlanCards(model: model, loop: loop, projection: projection)
            sections
            VStack(alignment: .leading, spacing: 4) {
                Text("plan.expected").font(CuadraoTypography.section)
                ForEach(Array(projection.occurrences.prefix(expanded ? projection.occurrences.count : 6))) { occurrence in
                    Button {
                        if let current = model.projection?.occurrences.first(where: { $0.id == occurrence.id }) {
                            Task { await model.open(current) }
                        }
                    } label: { FinancialOccurrenceRow(occurrence: occurrence) }
                        .buttonStyle(.plain).accessibilityIdentifier("plan.occurrence." + occurrence.id)
                }
                if projection.occurrences.count > 6 {
                    Button(expanded ? "plan.showLess" : "plan.showMore") { expanded.toggle() }.frame(minHeight: 44)
                        .accessibilityIdentifier("plan.showMore")
                }
            }
            PlanPrimaryButton(title: NSLocalizedString("plan.add.title", comment: ""), symbol: "plus") { model.create() }
                .accessibilityIdentifier("plan.add").disabled(loop.pendingConfirmation != nil || model.saving)
            if !projection.expectations.isEmpty {
                DisclosureGroup("plan.manageExpectations") {
                    ForEach(projection.expectations) { expectation in
                        Button {
                            if let current = model.projection?.expectations.first(where: { $0.id == expectation.id }) { model.edit(current) }
                        } label: {
                            HStack { Text(expectation.title); Spacer(); Image(systemName: "chevron.right") }.frame(minHeight: 48).contentShape(Rectangle())
                        }.buttonStyle(.plain).disabled(loop.pendingConfirmation != nil)
                            .accessibilityIdentifier("plan.expectation." + expectation.id.uuidString)
                    }
                }
            }
            Text("plan.assumptions").font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }
    }
    private var createKey: String {
        switch model.section {
        case .overview: "plan.add.title"
        case .goals: "goal.add"
        case .budgets: "budget.add"
        case .debts: "debt.add"
        }
    }
    private func create() {
        switch model.section {
        case .overview: model.create()
        case .goals: loop.goals.create()
        case .budgets: Task { await loop.budgets.create() }
        case .debts: loop.debts.create()
        }
    }
    private func includedNames(_ projection: FinancialPlanProjection) -> String {
        projection.accounts.filter { projection.selection.accountIds.contains($0.id) }.map {
            $0.nickname ?? NSLocalizedString("accounts.type." + $0.type, comment: "")
        }.joined(separator: " · ")
    }
}

struct FinancialForecastSummary: View {
    let currency: FinancialForecastCurrency
    /// Home and Plan both render a summary; distinct prefixes keep each total addressable.
    var identifier = "plan.projected."
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("plan.projectedBalance").font(ArgusStyle.body(14, relativeTo: .subheadline)).foregroundStyle(ArgusStyle.secondary)
            if let ending = currency.endingMinor {
                Text(verbatim: PlanPresentation.money(ending, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale))
                    .font(ArgusStyle.display(32)).monospacedDigit().fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier(identifier + currency.currency)
            } else {
                Text("accounts.unknown").font(ArgusStyle.display(28))
                Text(verbatim: currency.currency).font(ArgusStyle.body(14))
                Text("plan.unknown").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            if let asOf = currency.asOf {
                Text(verbatim: NSLocalizedString("plan.asOf", comment: "") + " " +
                     AccountPresentation.date(asOf, zone: TimeZone.current.identifier, locale: locale))
                    .font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
        }
    }
}

struct FinancialOccurrenceRow: View {
    let occurrence: FinancialPlanOccurrence
    @Environment(\.locale) private var locale
    @Environment(\.dynamicTypeSize) private var size
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(occurrence.title).font(CuadraoTypography.body)
                Spacer(minLength: 8)
                if !size.isAccessibilitySize { amount }
            }
            if size.isAccessibilitySize { amount }
            Text(verbatim: PlanPresentation.dateLabel(occurrence.dueDate, locale: locale))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            Text(LocalizedStringKey("plan.status." + occurrence.status.rawValue))
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            if occurrence.overdue { Text("plan.overdue").font(CuadraoTypography.caption) }
            if let reason = occurrence.exclusionReason {
                Text(LocalizedStringKey("plan.exclusion." + reason)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 16).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }.accessibilityElement(children: .combine)
    }
    private var amount: some View {
        Text(verbatim: (occurrence.kind == .income ? "+" : "−") + occurrence.currency + " " + AccountPresentation.amount(occurrence.amount, locale: locale))
            .font(CuadraoTypography.rowAmount)
    }
}

struct PlanValueRow: View {
    let title: LocalizedStringKey
    let value: String
    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack { Text(title); Spacer(minLength: 12); Text(verbatim: value).monospacedDigit() }
            VStack(alignment: .leading, spacing: 5) { Text(title); Text(verbatim: value).monospacedDigit() }
        }.font(ArgusStyle.body(13, relativeTo: .subheadline))
    }
}

struct PlanPendingView: View {
    @ObservedObject var loop: FinancialLoopModel
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(LocalizedStringKey(loop.pendingTitle)).font(ArgusStyle.body(15))
            Text("loop.pending.body").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            Button("loop.pending.retry") { Task { await loop.retryPending() } }
                .buttonStyle(PillButtonStyle()).disabled(loop.recovering).accessibilityIdentifier("loop.pending.retry")
            if let error = loop.recoveryErrorKey { Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary) }
        }.padding(16).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
    }
}

import SwiftUI
import Charts
import ArgusSession

struct FinancialPlanDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let showProfile: () -> Void
    var body: some View {
        if auth.state == .authenticated, let loop = auth.financialLoop {
            FinancialPlanView(model: loop.plan, loop: loop)
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
    @State private var selectingAccounts = false
    @State private var expanded = false
    @Environment(\.locale) private var locale

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                PersonalContext()
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 24) {
                        ForEach(PlanSection.allCases, id: \.self) { item in
                            Button { model.section = item } label: {
                                Text(item.title).font(ArgusStyle.body(14, relativeTo: .subheadline))
                                    .frame(minWidth: 44, minHeight: 48)
                                    .foregroundStyle(model.section == item ? ArgusStyle.ink : ArgusStyle.secondary)
                                    .overlay(alignment: .bottom) { Rectangle().fill(model.section == item ? ArgusStyle.ink : .clear).frame(height: 1) }.contentShape(Rectangle())
                            }.buttonStyle(.plain).accessibilityIdentifier("plan." + item.rawValue)
                                .accessibilityAddTraits(model.section == item ? .isSelected : [])
                        }
                    }
                }
                if model.section == .overview {
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    if let projection = model.projection { overview(projection) }
                    if model.loading { ProgressView("accounts.loading") }
                    if let error = model.errorKey {
                        Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                        Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44)
                    }
                } else if model.section == .goals {
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    FinancialGoalList(plan: model, model: loop.goals, origin: .plan)
                } else if model.section == .debts {
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    FinancialDebtList(plan: model, model: loop.debts, origin: .plan)
                } else if model.section == .budgets {
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    FinancialBudgetList(plan: model, model: loop.budgets, origin: .plan)
                } else {
                    Text(model.section.title).font(ArgusStyle.display())
                    Text("plan.unavailable").foregroundStyle(ArgusStyle.secondary)
                }
            }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, 24)
        }
        .task { if model.projection == nil { await model.refresh() } }
        .refreshable { await loop.refresh() }
        .sheet(isPresented: $selectingAccounts) {
            if let projection = model.projection { FinancialPlanSelectionView(model: model, loop: loop, projection: projection) }
        }
    }

    private func overview(_ projection: FinancialPlanProjection) -> some View {
        VStack(alignment: .leading, spacing: 28) {
            DatePicker("plan.until.label", selection: Binding(get: { PlanPresentation.date(projection.endDate) },
                set: { date in Task { await model.refresh(until: PlanPresentation.day(date)) } }),
                in: PlanPresentation.date(projection.startDate)...PlanPresentation.date(projection.startDate).addingTimeInterval(366 * 86400),
                displayedComponents: .date)
                .environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                .font(ArgusStyle.body(14, relativeTo: .subheadline)).accessibilityIdentifier("plan.until")
            if projection.selection.accountIds.isEmpty {
                Text("plan.chooseMoney").font(ArgusStyle.display(30))
            }
            ForEach(projection.currencies) { currency in
                VStack(alignment: .leading, spacing: 16) {
                    FinancialForecastSummary(currency: currency)
                    if !currency.points.isEmpty, currency.unknownAccountIds.isEmpty {
                        FinancialForecastChart(currency: currency)
                    }
                    PlanValueRow(title: "plan.income", value: amount(currency.expectedIncomeMinor, currency))
                    PlanValueRow(title: "plan.bills", value: amount(currency.expectedBillsMinor, currency))
                    if let effect = currency.transferEffectMinor { PlanValueRow(title: "goal.transferEffect", value: amount(effect, currency)) }
                    PlanValueRow(title: "plan.netChange", value: amount(currency.netCashChangeMinor, currency))
                    if let shortfall = currency.firstShortfallDate {
                        Label { Text("plan.shortfall") + Text(verbatim: " · " + PlanPresentation.dateLabel(shortfall, locale: locale)) }
                            icon: { Image(systemName: "exclamationmark.circle") }
                            .font(ArgusStyle.body(13, relativeTo: .subheadline)).accessibilityIdentifier("plan.shortfall." + currency.currency)
                    }
                }
            }
            Button { selectingAccounts = true } label: {
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text("plan.includedAccounts"); Spacer(); Image(systemName: "chevron.right").font(.system(size: 12)) }
                    Text(includedNames(projection)).font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                }.frame(minHeight: 48).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("plan.accounts").disabled(loop.pendingConfirmation != nil)
            Text(verbatim: projection.selection.timeZone).font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            if !projection.hasExpectations { Text("plan.empty").foregroundStyle(ArgusStyle.secondary) }
            VStack(alignment: .leading, spacing: 4) {
                Text("plan.expected").font(ArgusStyle.display(23))
                ForEach(Array(projection.occurrences.prefix(expanded ? projection.occurrences.count : 6))) { occurrence in
                    Button { Task { await model.open(occurrence) } } label: { FinancialOccurrenceRow(occurrence: occurrence) }
                        .buttonStyle(.plain).accessibilityIdentifier("plan.occurrence." + occurrence.id)
                }
                if projection.occurrences.count > 6 {
                    Button(expanded ? "plan.showLess" : "plan.showMore") { expanded.toggle() }.frame(minHeight: 44)
                        .accessibilityIdentifier("plan.showMore")
                }
            }
            Button("plan.add.title") { model.create() }.buttonStyle(PillButtonStyle())
                .accessibilityIdentifier("plan.add").disabled(loop.pendingConfirmation != nil || model.saving)
            if !projection.expectations.isEmpty {
                DisclosureGroup("plan.manageExpectations") {
                    ForEach(projection.expectations) { expectation in
                        Button { model.edit(expectation) } label: {
                            HStack { Text(expectation.title); Spacer(); Image(systemName: "chevron.right") }.frame(minHeight: 48).contentShape(Rectangle())
                        }.buttonStyle(.plain).disabled(loop.pendingConfirmation != nil)
                            .accessibilityIdentifier("plan.expectation." + expectation.id.uuidString)
                    }
                }
            }
            Text("plan.assumptions").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
        }
    }
    private func amount(_ minor: String, _ currency: FinancialForecastCurrency) -> String {
        PlanPresentation.money(minor, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale)
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

struct FinancialForecastChart: View {
    let currency: FinancialForecastCurrency
    @State private var selected: Int?
    @Environment(\.locale) private var locale
    private var indices: [Int] { Array(currency.points.indices) }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Chart(indices, id: \.self) { index in
                if let minor = currency.points[index].balanceMinor, let value = Double(minor) {
                    LineMark(x: .value("Step", index), y: .value("Balance", value))
                        .foregroundStyle(ArgusStyle.ink).lineStyle(StrokeStyle(lineWidth: 2)).interpolationMethod(.linear)
                    if selected == index || indices.count == 1 {
                        PointMark(x: .value("Step", index), y: .value("Balance", value)).foregroundStyle(ArgusStyle.ink)
                        RuleMark(x: .value("Step", index)).foregroundStyle(ArgusStyle.secondary.opacity(0.4))
                    }
                }
            }
            .chartYAxis(.hidden)
            .chartXAxis {
                AxisMarks(values: Array(Set([0, max(0, indices.count / 2), max(0, indices.count - 1)])).sorted()) { value in
                    AxisValueLabel {
                        if let index = value.as(Int.self), indices.contains(index) {
                            Text(verbatim: PlanPresentation.dateLabel(currency.points[index].date, locale: locale))
                                .font(ArgusStyle.body(10, relativeTo: .caption2))
                        }
                    }
                }
            }
            .chartXSelection(value: $selected)
            .frame(height: 210).accessibilityIdentifier("plan.chart")
            .accessibilityLabel("plan.chart.title")
            Text("plan.chart.title").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            if let selected, indices.contains(selected), let minor = currency.points[selected].balanceMinor {
                Text(verbatim: PlanPresentation.dateLabel(currency.points[selected].date, locale: locale) + " · " +
                     PlanPresentation.money(minor, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale))
                    .font(ArgusStyle.body(12, relativeTo: .caption)).monospacedDigit().accessibilityIdentifier("plan.chart.readout")
            } else { Text("plan.chart.inspect").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary) }
            Stepper("plan.chart.accessibility", value: Binding(get: { selected ?? 0 }, set: { selected = $0 }), in: 0...max(0, indices.count - 1))
                .font(ArgusStyle.body(12, relativeTo: .caption)).accessibilityIdentifier("plan.chart.step")
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
                Text(occurrence.title).font(ArgusStyle.body(15))
                Spacer(minLength: 8)
                if !size.isAccessibilitySize { amount }
            }
            if size.isAccessibilitySize { amount }
            Text(verbatim: PlanPresentation.dateLabel(occurrence.dueDate, locale: locale))
                .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            Text(LocalizedStringKey("plan.status." + occurrence.status.rawValue))
                .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            if occurrence.overdue { Text("plan.overdue").font(ArgusStyle.body(12, relativeTo: .caption)) }
            if let reason = occurrence.exclusionReason {
                Text(LocalizedStringKey("plan.exclusion." + reason)).font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
        }.padding(.vertical, 16).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }.accessibilityElement(children: .combine)
    }
    private var amount: some View {
        Text(verbatim: (occurrence.kind == .income ? "+" : "−") + occurrence.currency + " " + AccountPresentation.amount(occurrence.amount, locale: locale))
            .font(ArgusStyle.body(13, relativeTo: .subheadline)).monospacedDigit()
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

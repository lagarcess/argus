import SwiftUI
import ArgusSession

struct FinancialBudgetList: View {
    @ObservedObject var plan: FinancialPlanModel
    @ObservedObject var model: FinancialBudgetModel
    let origin: FinancialBudgetNavigation.Origin
    var compact = false
    private var items: [FinancialBudgetProgress] { (plan.projection?.budgets ?? []).filter { !$0.budget.archived } }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("plan.budgets").font(ArgusStyle.display(23))
            if items.isEmpty { Text("budget.empty").foregroundStyle(ArgusStyle.secondary) }
            ForEach(items) { progress in
                Button { Task { await model.open(progress.id, origin: origin) } } label: {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack { Text(verbatim: progress.budget.name); Spacer(); Image(systemName: "chevron.right").font(.system(size: 12)) }
                        FinancialBudgetSummary(progress: progress, compact: true)
                    }.padding(.vertical, 14).contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityIdentifier("budget.row." + progress.id.uuidString)
            }
            if !compact {
                Button("budget.add") { Task { await model.create() } }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("budget.add")
                if let archived = plan.projection?.budgets.filter({ $0.budget.archived }), !archived.isEmpty {
                    DisclosureGroup("budget.archived") {
                        ForEach(archived) { progress in
                            Button { Task { await model.open(progress.id, origin: origin) } } label: {
                                HStack { Text(verbatim: progress.budget.name); Spacer(); Image(systemName: "chevron.right") }.frame(minHeight: 48)
                            }.buttonStyle(.plain).accessibilityIdentifier("budget.archived." + progress.id.uuidString)
                        }
                    }
                }
            }
        }
    }
}

struct FinancialBudgetSummary: View {
    let progress: FinancialBudgetProgress
    var compact = false
    @Environment(\.locale) private var locale
    private func amount(_ value: String) -> String {
        PlanPresentation.money(value, currency: progress.budget.currency, digits: progress.budget.currencyFractionDigits, locale: locale)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 8 : 16) {
            Text(verbatim: amount(progress.spentMinor)).font(ArgusStyle.display(compact ? 23 : 34)).monospacedDigit()
                .accessibilityIdentifier("budget.spent")
            HStack(spacing: 4) {
                Text("budget.of"); Text(verbatim: amount(String(progress.budget.limitMinor)))
            }.font(ArgusStyle.body(13, relativeTo: .subheadline)).foregroundStyle(ArgusStyle.secondary)
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule().fill(ArgusStyle.line)
                    Capsule().fill(ArgusStyle.teal).frame(width: geometry.size.width * progress.meterFraction)
                }
            }.frame(height: 4).accessibilityHidden(true)
            HStack(spacing: 4) {
                Text(verbatim: amount(progress.isOverBudget ? progress.overBudgetMinor : progress.remainingMinor))
                Text(progress.isOverBudget ? "budget.over" : "budget.remaining")
            }.font(ArgusStyle.body(13, relativeTo: .subheadline)).foregroundStyle(progress.isOverBudget ? ArgusStyle.negative : ArgusStyle.secondary)
                .accessibilityElement(children: .combine).accessibilityIdentifier("budget.remaining")
        }
    }
}

struct FinancialBudgetPresenter: View {
    @ObservedObject var model: FinancialBudgetModel
    @ObservedObject var loop: FinancialLoopModel
    @Binding var destination: AppDestination
    let search: FinancialSearchModel?
    var body: some View {
        ZStack {
            if model.navigation != nil {
                Color.black.opacity(0.25).ignoresSafeArea()
                FinancialBudgetDetailView(model: model, loop: loop) {
                    if let origin = model.navigation?.origin {
                        switch origin { case .home: destination = .home; case .plan: destination = .plan; loop.plan.section = .budgets; case .search: destination = .search }
                    }
                    model.close()
                    Task { await search?.refresh() }
                }.background(ArgusStyle.background).clipShape(RoundedRectangle(cornerRadius: 24))
                    .padding(12).accessibilityElement(children: .contain).accessibilityIdentifier("budget.detail")
            } else { Color.clear.allowsHitTesting(false) }
        }
        .sheet(item: $model.draft, onDismiss: { Task { await search?.refresh() } }) { draft in
            FinancialBudgetForm(model: model, loop: loop, draft: draft)
        }
    }
}

struct FinancialBudgetDetailView: View {
    @ObservedObject var model: FinancialBudgetModel
    @ObservedObject var loop: FinancialLoopModel
    let close: () -> Void
    @State private var removing = false
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                if model.navigation?.activityID != nil {
                    Button { model.activity(nil); Task { await model.refreshIfOpen() } } label: { Label("budget.back", systemImage: "chevron.left") }
                        .accessibilityIdentifier("budget.activity.back")
                }
                if model.navigation?.activityID == nil, let progress = model.detail {
                    Text(verbatim: progress.budget.name).font(ArgusStyle.display(23))
                }
                Spacer()
                Button(action: close) { Image(systemName: "xmark").frame(width: 48, height: 48) }
                    .accessibilityLabel("action.close").accessibilityIdentifier("budget.close")
            }.padding(.horizontal, 20)
            if let id = model.navigation?.activityID {
                ScrollView { FinancialActivityDetailView(loop: loop, activityID: id) { loop.correct($0) }.padding(24) }
            } else {
                ScrollViewReader { reader in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            if let progress = model.detail {
                                Text(verbatim: month(progress.budget.month)).foregroundStyle(ArgusStyle.secondary)
                                FinancialBudgetSummary(progress: progress)
                                scope(progress)
                                Text("budget.recordedOnly").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                                Text("budget.contributors").font(ArgusStyle.display(21))
                                if progress.contributors.isEmpty { Text("budget.noActivity").foregroundStyle(ArgusStyle.secondary) }
                                ForEach(progress.contributors, id: \.activityId) { item in
                                    Button { model.activity(item.activityId) } label: { contributor(item) }
                                        .buttonStyle(.plain).id(item.activityId).accessibilityIdentifier("budget.activity." + item.activityId.uuidString)
                                }
                                if progress.budget.archived {
                                    Text("budget.archived").foregroundStyle(ArgusStyle.secondary)
                                    Button("budget.restore") { Task { await model.archive(false) } }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("budget.restore")
                                } else {
                                    Button("budget.edit") { Task { await model.edit() } }.buttonStyle(PillButtonStyle(primary: false)).accessibilityIdentifier("budget.edit")
                                    Button("budget.remove", role: .destructive) { removing = true }.frame(minHeight: 48).accessibilityIdentifier("budget.remove")
                                }
                            }
                            if model.loading { ProgressView("accounts.loading") }
                            if let error = model.errorKey {
                                Text(LocalizedStringKey(error)).accessibilityIdentifier("budget.error")
                                Button("accounts.retry") { Task { await model.refreshIfOpen() } }.frame(minHeight: 44)
                            }
                            if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                        }.padding(24).disabled(model.saving)
                    }.task(id: model.detail?.contributors.map(\.activityId)) {
                        guard let anchor = model.navigation?.anchor,
                              model.detail?.contributors.contains(where: { $0.activityId == anchor }) == true else { return }
                        await Task.yield()
                        guard !Task.isCancelled else { return }
                        reader.scrollTo(anchor, anchor: .top)
                    }
                }
            }
        }.background(ArgusStyle.background)
            .confirmationDialog("budget.remove.confirm", isPresented: $removing, titleVisibility: .visible) {
                Button("budget.remove", role: .destructive) { Task { await model.archive(true) } }.accessibilityIdentifier("budget.remove.confirm")
                Button("accounts.cancel", role: .cancel) { }
            } message: { Text("budget.remove.body") }
    }
    private func month(_ value: String) -> String {
        let formatter = DateFormatter(); formatter.locale = locale; formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.setLocalizedDateFormatFromTemplate("MMMM yyyy")
        return formatter.string(from: PlanPresentation.date(value + "-01"))
    }
    private func scope(_ progress: FinancialBudgetProgress) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(progress.budget.accountIds.map(loop.accountName).joined(separator: " · "))
            Text((progress.budget.categoryIds.map { NSLocalizedString("loop.category." + $0, comment: "") } +
                (progress.budget.includeUncategorized ? [NSLocalizedString("budget.uncategorized", comment: "")] : [])).joined(separator: " · "))
            Text(verbatim: progress.period.timeZone)
            Text(verbatim: AccountPresentation.date(progress.period.startAt, zone: progress.period.timeZone, locale: locale) + " → " +
                AccountPresentation.date(progress.period.endAtExclusive, zone: progress.period.timeZone, locale: locale))
            Text("budget.interval.hint")
        }.font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary).accessibilityIdentifier("budget.scope")
    }
    private func contributor(_ item: FinancialActivityDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(item.note ?? NSLocalizedString("loop.kind." + item.kind.rawValue, comment: ""))
                Spacer(minLength: 12)
                Text(verbatim: (item.kind == .refund ? "−" : "") + item.currency + " " + AccountPresentation.amount(item.amount, locale: locale)).monospacedDigit()
            }
            Text((item.legs.first.map { loop.accountName($0.accountId) } ?? "") + " · " + AccountPresentation.date(item.occurredAt, zone: item.timeZone, locale: locale))
                .font(ArgusStyle.body(11, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
        }.font(ArgusStyle.body(14)).padding(.vertical, 16).frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle()).overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
    }
}


private struct FinancialBudgetOcclusion: ViewModifier {
    @ObservedObject var model: FinancialBudgetModel
    func body(content: Content) -> some View {
        content.accessibilityHidden(model.navigation != nil).allowsHitTesting(model.navigation == nil)
    }
}

extension View {
    @ViewBuilder func financialBudgetBackground(_ model: FinancialBudgetModel?) -> some View {
        if let model { modifier(FinancialBudgetOcclusion(model: model)) } else { self }
    }
}

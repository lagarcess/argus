import SwiftUI
import ArgusSession

struct FinancialGoalList: View {
    @ObservedObject var plan: FinancialPlanModel
    @ObservedObject var model: FinancialGoalModel
    let origin: FinancialGoalNavigation.Origin
    var compact = false
    private var items: [FinancialGoalProgress] { (plan.projection?.goals ?? []).filter { !$0.goal.archived } }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("plan.goals").font(ArgusStyle.display(23))
            if items.isEmpty { Text("goal.empty").foregroundStyle(ArgusStyle.secondary) }
            ForEach(items) { progress in
                Button { Task { await model.open(progress.id, origin: origin) } } label: {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack { Text(verbatim: progress.goal.name); Spacer(); Image(systemName: "chevron.right").font(.system(size: 12)) }
                        FinancialGoalSummary(progress: progress, compact: true)
                    }.padding(.vertical, 14).contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityIdentifier("goal.row." + origin.rawValue + "." + progress.id.uuidString)
            }
            if !compact {
                Button("goal.add") { model.create() }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("goal.add")
                if let archived = plan.projection?.goals?.filter({ $0.goal.archived }), !archived.isEmpty {
                    DisclosureGroup("goal.archived") {
                        ForEach(archived) { progress in
                            Button { Task { await model.open(progress.id, origin: origin) } } label: {
                                HStack { Text(verbatim: progress.goal.name); Spacer(); Image(systemName: "chevron.right") }.frame(minHeight: 48)
                            }.buttonStyle(.plain).accessibilityIdentifier("goal.archived." + progress.id.uuidString)
                        }
                    }
                }
            }
        }
    }
}

struct FinancialGoalSummary: View {
    let progress: FinancialGoalProgress
    var compact = false
    @Environment(\.locale) private var locale
    private func amount(_ value: String?) -> String {
        value.map { PlanPresentation.money($0, currency: progress.goal.currency, digits: progress.goal.currencyFractionDigits, locale: locale) } ?? NSLocalizedString("goal.needsReview", comment: "")
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("goal.supported").foregroundStyle(ArgusStyle.secondary)
            Text(verbatim: amount(progress.supportedMinor)).font(ArgusStyle.display(compact ? 23 : 34)).monospacedDigit().accessibilityIdentifier("goal.supported")
            if let fraction = progress.meterFraction {
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        Capsule().fill(ArgusStyle.line)
                        Capsule().fill(ArgusStyle.teal).frame(width: geometry.size.width * fraction)
                    }
                }.frame(height: 4).accessibilityHidden(true)
            }
            Text(LocalizedStringKey("goal.state." + progress.state)).foregroundStyle(progress.state == "needs_review" ? ArgusStyle.negative : ArgusStyle.secondary).accessibilityIdentifier("goal.state")
            if compact {
                HStack(spacing: 4) { Text("goal.of"); Text(verbatim: amount(String(progress.goal.targetMinor))) }
                    .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                PlanValueRow(title: "goal.remaining", value: amount(progress.remainingMinor))
            }
            if !compact {
                PlanValueRow(title: "goal.target", value: amount(String(progress.goal.targetMinor)))
                PlanValueRow(title: "goal.assigned", value: amount(progress.assignedMinor)).accessibilityIdentifier("goal.assigned")
                PlanValueRow(title: "goal.remaining", value: amount(progress.remainingMinor))
                if progress.supportedMinor == nil { PlanValueRow(title: "goal.partial", value: amount(progress.independentlyBackedMinor)) }
                if let targetDate = progress.goal.targetDate { PlanValueRow(title: "goal.targetDate", value: PlanPresentation.dateLabel(targetDate, locale: locale)) }
                Text("goal.plan").font(ArgusStyle.display(21))
                PlanValueRow(title: "goal.planned", value: amount(progress.plannedMinor))
                PlanValueRow(title: "goal.projected", value: amount(progress.projectedMinor))
                Text(PlanPresentation.dateLabel(progress.projectionEndDate, locale: locale)).foregroundStyle(ArgusStyle.secondary)
                Text("goal.plan.disclosure").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
        }
    }
}

struct FinancialGoalPresenter: View {
    @ObservedObject var model: FinancialGoalModel
    @ObservedObject var loop: FinancialLoopModel
    @Binding var destination: AppDestination
    let search: FinancialSearchModel?
    var body: some View {
        ZStack {
            if model.navigation != nil {
                Color.black.opacity(0.25).ignoresSafeArea()
                FinancialGoalDetail(model: model, loop: loop) {
                    if let origin = model.navigation?.origin {
                        switch origin { case .home: destination = .home; case .plan: destination = .plan; loop.plan.section = .goals; case .search: destination = .search }
                    }
                    model.close(); Task { await search?.refresh() }
                }.background(ArgusStyle.background).clipShape(RoundedRectangle(cornerRadius: 24)).padding(12)
                    .accessibilityElement(children: .contain).accessibilityIdentifier("goal.detail")
            } else { Color.clear.allowsHitTesting(false) }
        }
        .sheet(item: $model.draft, onDismiss: { Task { await search?.refresh() } }) { draft in
            FinancialGoalForm(model: model, loop: loop, draft: draft)
        }
        .sheet(item: $model.action) { action in
            if let detail = model.detail {
                switch action {
                case .allocation: FinancialGoalAllocationView(model: model, loop: loop, detail: detail)
                case .link: FinancialGoalLinkView(model: model, loop: loop)
                }
            }
        }
    }
}

struct FinancialGoalDetail: View {
    @ObservedObject var model: FinancialGoalModel
    @ObservedObject var loop: FinancialLoopModel
    let close: () -> Void
    @State private var archiving = false
    @State private var releasing: FinancialGoalContribution?
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                if model.navigation?.activityID != nil {
                    Button { model.activity(nil); Task { await model.refreshIfOpen() } } label: { Label("goal.back", systemImage: "chevron.left") }.accessibilityIdentifier("goal.activity.back")
                } else if let detail = model.detail { Text(verbatim: detail.goal.name).font(ArgusStyle.display(23)) }
                Spacer()
                Button(action: close) { Image(systemName: "xmark").frame(width: 48, height: 48) }.accessibilityLabel("action.close").accessibilityIdentifier("goal.close")
            }.padding(.horizontal, 20)
            if let id = model.navigation?.activityID {
                ScrollView { FinancialActivityDetailView(loop: loop, activityID: id) { loop.correct($0) }.padding(24) }
            } else {
                ScrollViewReader { reader in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            if let progress = model.detail {
                                FinancialGoalSummary(progress: progress)
                                if let destination = progress.goal.destinationAccountId { PlanValueRow(title: "goal.destination", value: loop.accountName(destination)) }
                                ForEach(progress.pools) { pool in
                                    VStack(alignment: .leading, spacing: 10) {
                                        Text(loop.accountName(pool.accountId)).font(ArgusStyle.display(20))
                                        PlanValueRow(title: "goal.backing", value: money(pool.backingMinor, progress))
                                        PlanValueRow(title: "goal.shortfall", value: money(pool.shortfallMinor, progress)).accessibilityIdentifier("goal.pool.shortfall." + pool.accountId.uuidString)
                                        Text(pool.affectedGoalNames.joined(separator: " · ")).foregroundStyle(ArgusStyle.secondary)
                                        if let asOf = pool.asOf { Text(AccountPresentation.date(asOf, zone: loop.plan.projection?.selection.timeZone ?? "UTC", locale: locale)).font(ArgusStyle.body(12, relativeTo: .caption)) }
                                    }
                                }
                                ForEach(progress.reasons, id: \.self) { Text(LocalizedStringKey("goal.reason." + $0)).foregroundStyle(ArgusStyle.negative) }
                                Button("goal.allocate") { model.action = .allocation }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("goal.allocate")
                                if progress.goal.destinationAccountId != nil {
                                    Button("goal.record") { model.record() }.buttonStyle(PillButtonStyle(primary: false)).accessibilityIdentifier("goal.record")
                                    Button("goal.link") { Task { await model.loadCandidates() } }.frame(minHeight: 48).accessibilityIdentifier("goal.link")
                                }
                                Text("goal.contributions").font(ArgusStyle.display(21))
                                if progress.contributions.isEmpty { Text("goal.noContributions").foregroundStyle(ArgusStyle.secondary) }
                                ForEach(progress.contributions) { claim in
                                    VStack(alignment: .leading, spacing: 8) {
                                        Button { model.activity(claim.activityId) } label: {
                                            HStack {
                                                Text(claim.activity?.note ?? NSLocalizedString("loop.kind.transfer", comment: ""))
                                                Spacer(); Text(verbatim: money(claim.currentPersonalMinor, progress))
                                                Image(systemName: "chevron.right")
                                            }.frame(minHeight: 48).contentShape(Rectangle())
                                        }.buttonStyle(.plain).accessibilityIdentifier("goal.activity." + claim.activityId.uuidString)
                                        Text(LocalizedStringKey("goal.contribution." + claim.status)).foregroundStyle(ArgusStyle.secondary)
                                        if claim.counting {
                                            Button("goal.stopCounting") { releasing = claim }.frame(minHeight: 44).accessibilityIdentifier("goal.release." + claim.id.uuidString)
                                        }
                                    }.id(claim.activityId)
                                }
                                if progress.goal.archived {
                                    Text("goal.archived")
                                    Button("goal.restore") { Task { await model.archive(false) } }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("goal.restore")
                                } else {
                                    Button("goal.edit") { model.edit() }.buttonStyle(PillButtonStyle(primary: false)).accessibilityIdentifier("goal.edit")
                                    Button("goal.archive") { archiving = true }.frame(minHeight: 48).accessibilityIdentifier("goal.archive")
                                }
                            }
                            if model.loading { ProgressView("goal.loading") }
                            if let error = model.errorKey {
                                Text(LocalizedStringKey(error)).accessibilityIdentifier("goal.error")
                                Button("accounts.retry") { Task { await model.refreshIfOpen() } }
                            }
                            if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                        }.padding(24).disabled(model.saving)
                    }.task(id: model.detail?.contributions.map(\.activityId)) {
                        guard let anchor = model.navigation?.anchor else { return }
                        await Task.yield(); guard !Task.isCancelled else { return }; reader.scrollTo(anchor, anchor: .top)
                    }
                }
            }
        }.confirmationDialog("goal.archive", isPresented: $archiving, titleVisibility: .visible) {
            Button("goal.archive") { Task { await model.archive(true) } }.accessibilityIdentifier("goal.archive.confirm")
            Button("accounts.cancel", role: .cancel) { }
        } message: { Text("goal.archive.disclosure") }
        .confirmationDialog("goal.stopCounting", isPresented: Binding(get: { releasing != nil }, set: { if !$0 { releasing = nil } }), titleVisibility: .visible) {
            if let claim = releasing { Button("goal.stopCounting") { Task { await model.release(claim) } }.accessibilityIdentifier("goal.release.confirm") }
            Button("accounts.cancel", role: .cancel) { releasing = nil }
        } message: { Text("goal.release.disclosure") }
    }
    private func money(_ minor: String?, _ progress: FinancialGoalProgress) -> String {
        minor.map { PlanPresentation.money($0, currency: progress.goal.currency, digits: progress.goal.currencyFractionDigits, locale: locale) } ?? NSLocalizedString("accounts.unknown", comment: "")
    }
}

private struct FinancialGoalOcclusion: ViewModifier {
    @ObservedObject var model: FinancialGoalModel
    func body(content: Content) -> some View { content.accessibilityHidden(model.navigation != nil).allowsHitTesting(model.navigation == nil) }
}
extension View {
    @ViewBuilder func financialGoalBackground(_ model: FinancialGoalModel?) -> some View {
        if let model { modifier(FinancialGoalOcclusion(model: model)) } else { self }
    }
}

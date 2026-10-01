import SwiftUI
import ArgusSession

struct HouseholdPlanContent: View {
    @ObservedObject var model: HouseholdPlanModel
    var compact = false
    var origin = HouseholdPlanModel.Origin.plan
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("sharedPlan.title").font(ArgusStyle.display(25))
                Spacer()
                if model.canStart {
                    Menu {
                        Button("sharedPlan.create") { model.show(.create) }.accessibilityIdentifier("sharedPlan.create")
                        Button("sharedPlan.share") { model.show(.share) }.accessibilityIdentifier("sharedPlan.share")
                    } label: { Image(systemName: "plus").frame(width: 44, height: 44) }
                    .accessibilityLabel("sharedPlan.create").accessibilityIdentifier("sharedPlan.add")
                }
            }
            Text("sharedPlan.privacy").font(ArgusStyle.body(13, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            if model.state == .idle || model.state == .loading { ProgressView("accounts.loading").accessibilityIdentifier("sharedPlan.loading") }
            if model.state == .unavailable {
                Text(LocalizedStringKey(model.errorKey ?? "household.loadError"))
                Button("accounts.retry") { Task { await model.refresh() } }.accessibilityIdentifier("sharedPlan.retry").frame(minHeight: 44)
            }
            if model.state == .ready {
                if model.plans.isEmpty { Text("sharedPlan.empty").foregroundStyle(ArgusStyle.secondary).accessibilityIdentifier("sharedPlan.empty") }
                ForEach(compact ? Array(model.plans.filter { !$0.archived }.prefix(4)) : model.plans) { plan in
                    Button { Task { await model.open(plan.ref, origin: origin) } } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(plan.definition.common.name).font(ArgusStyle.display(21))
                                Spacer(); Image(systemName: "chevron.right").font(.system(size: 13))
                            }
                            HStack {
                                Text(LocalizedStringKey("sharedPlan.kind." + plan.ref.kind.rawValue))
                                Spacer()
                                Text(plan.archived ? "sharedPlan.archived" : LocalizedStringKey("sharedPlan.state." + plan.progress.common.state.rawValue))
                            }.font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                            HouseholdPlanSummary(plan: plan, compact: true)
                        }.padding(.vertical, 12).frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("sharedPlan.row." + plan.ref.kind.rawValue + "." + plan.id.uuidString)
                    Divider()
                }
            }
        }
    }
}

struct HouseholdPlanSummary: View {
    let plan: HouseholdPlan
    var compact = false
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            switch plan.progress {
            case .budget(let c, let gross, let refunds, let spent, let over):
                value("sharedPlan.spent", spent)
                if !compact { value("sharedPlan.limit", plan.definition.amountMinor); value("sharedPlan.gross", gross); value("sharedPlan.refunds", refunds); value("sharedPlan.remaining", c.remainingMinor) }
                if over == true { Text("sharedPlan.overBudget").foregroundStyle(ArgusStyle.negative) }
            case .goal(let c, let planned, let projected):
                value("sharedPlan.actual", c.actualMinor)
                if !compact { value("sharedPlan.target", plan.definition.amountMinor); value("sharedPlan.planned", planned); value("sharedPlan.projected", projected); value("sharedPlan.remaining", c.remainingMinor); Text("sharedPlan.plannedNotice").font(.footnote).foregroundStyle(ArgusStyle.secondary) }
            case .bill(let c):
                value("sharedPlan.paid", c.appliedMinor)
                if !compact { value("sharedPlan.agreed", plan.definition.amountMinor); value("sharedPlan.remaining", c.remainingMinor) }
            case .debt(let c):
                value("sharedPlan.balance", c.debtBalanceMinor)
                if !compact { value("sharedPlan.paid", c.appliedMinor); value("sharedPlan.agreed", plan.definition.amountMinor); value("sharedPlan.remaining", c.remainingMinor) }
            }
        }
    }
    private func value(_ key: LocalizedStringKey, _ minor: String?) -> some View {
        HStack { Text(key); Spacer(); Text(HouseholdPlanPresentation.money(minor, plan: plan)).monospacedDigit() }
            .font(ArgusStyle.body(14))
    }
}

struct HouseholdPlanDetailView: View {
    @ObservedObject var model: HouseholdPlanModel
    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            Button("accounts.back") { model.back() }.frame(minHeight: 44).accessibilityIdentifier("sharedPlan.back")
            if model.detailLoading { ProgressView("accounts.loading") }
            if let error = model.errorKey {
                Text(LocalizedStringKey(error)).accessibilityIdentifier("sharedPlan.error")
                if !model.detailMissing, let ref = model.openedRef {
                    Button("accounts.retry") { Task { await model.open(ref, origin: model.origin) } }.frame(minHeight: 44)
                }
            }
            if let plan = model.detail {
                Text(plan.definition.common.name).font(ArgusStyle.display(30)).accessibilityIdentifier("sharedPlan.detail.name")
                Text(LocalizedStringKey("sharedPlan.kind." + plan.ref.kind.rawValue)).foregroundStyle(ArgusStyle.secondary)
                if plan.archived {
                    Text(plan.archiveReason == "owner_departed" ? "sharedPlan.ownerDeparted" : "sharedPlan.archivedNotice")
                        .font(.footnote).accessibilityIdentifier("sharedPlan.archiveNotice")
                }
                HouseholdPlanSummary(plan: plan)
                if !plan.archived, let schedule = plan.definition.schedule {
                    Text(LocalizedStringKey("plan.repeat." + schedule.cadence.rawValue)) + Text(" · " + schedule.startDate)
                }
                if case .budget(_, _, let month, let categories, let uncategorized, _) = plan.definition {
                    Text(month)
                    Text(categories.map { NSLocalizedString("loop.category." + $0, comment: "") }.joined(separator: ", "))
                    if uncategorized { Text("budget.uncategorized") }
                }
                HStack {
                    if plan.canEdit { Button("sharedPlan.edit") { model.show(.edit(plan)) }.accessibilityIdentifier("sharedPlan.edit").frame(minHeight: 44) }
                    if plan.canEdit || plan.canManagePeople { Button("household.people") { model.show(.people(plan)) }.accessibilityIdentifier("sharedPlan.people").frame(minHeight: 44) }
                    Spacer()
                }
                VStack(alignment: .leading, spacing: 12) {
                    Text("sharedPlan.team").font(ArgusStyle.display(22))
                    Text(plan.owner.displayName + " · " + NSLocalizedString("sharedPlan.owner", comment: ""))
                    ForEach(plan.participants) { person in
                        HStack { Text(person.displayName); Spacer(); Text(LocalizedStringKey("household.permission." + person.permission.rawValue)).foregroundStyle(ArgusStyle.secondary) }
                    }
                    ForEach(Array(plan.responsibilities.enumerated()), id: \.offset) { _, item in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack { Text(item.person.displayName); Spacer(); Text(item.amountMinor.map { HouseholdPlanPresentation.money($0, plan: plan) } ?? NSLocalizedString("sharedPlan.unassigned", comment: "")) }
                            Text(HouseholdPlanPresentation.period(item, plan: plan)).font(.footnote).foregroundStyle(ArgusStyle.secondary)
                        }.accessibilityIdentifier("sharedPlan.responsibility.value." + item.person.id.uuidString)
                    }
                    Text("sharedPlan.responsibilityNotice").font(.footnote).foregroundStyle(ArgusStyle.secondary)
                }
                if !plan.archived {
                    ForEach(plan.occurrences) { item in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack { Text(item.date); Spacer(); Text(HouseholdPlanPresentation.money(item.amountMinor, plan: plan)) }
                            HStack { Text(LocalizedStringKey("sharedPlan.occurrence." + item.status.rawValue)); Spacer(); Text(HouseholdPlanPresentation.money(item.remainingMinor, plan: plan)) }
                                .font(.footnote).foregroundStyle(ArgusStyle.secondary)
                        }.accessibilityIdentifier("sharedPlan.occurrence." + item.id.uuidString)
                    }
                }
                if plan.ref.kind == .goal {
                    ForEach(plan.allocations, id: \.id) { allocation in
                        HStack { Text(allocation.person.displayName); Spacer(); Text(HouseholdPlanPresentation.money(allocation.supportedMinor, plan: plan)) }
                    }
                    if plan.canContribute { Button("sharedPlan.allocate") { model.show(.allocation(plan)) }.frame(minHeight: 44).accessibilityIdentifier("sharedPlan.allocate") }
                }
                if plan.canContribute {
                    HStack {
                        Button("sharedPlan.record") { model.show(.record(plan, nil)) }.buttonStyle(PillButtonStyle()).accessibilityIdentifier("sharedPlan.record")
                        Button("sharedPlan.link") { model.show(.link(plan)) }.frame(minHeight: 44).accessibilityIdentifier("sharedPlan.link")
                    }
                }
                if !plan.contributions.isEmpty { Text("sharedPlan.contributions").font(ArgusStyle.display(22)) }
                ForEach(plan.contributions) { contribution in contributionRow(contribution, plan: plan) }
                Button("sharedPlan.history") { Task { await model.loadHistory(plan) } }.frame(minHeight: 44).accessibilityIdentifier("sharedPlan.history")
                ForEach(Array(model.history.enumerated()), id: \.offset) { _, previous in
                    VStack(alignment: .leading) {
                        Text(previous.definition.common.name + " · " + String(previous.version))
                        Text(previous.archived ? "sharedPlan.archived" : "sharedPlan.active").font(.footnote)
                    }.accessibilityIdentifier("sharedPlan.history." + String(previous.version))
                }
                if plan.canEdit || plan.canRestore {
                    Button(plan.archived ? "sharedPlan.restore" : "sharedPlan.archive") { Task { await model.archive(plan) } }
                        .frame(minHeight: 44).accessibilityIdentifier(plan.archived ? "sharedPlan.restore" : "sharedPlan.archive").disabled(model.pending || model.busy)
                }
            }
        }
    }
    private func contributionRow(_ item: HouseholdPlanContribution, plan: HouseholdPlan) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { Text(item.person.displayName); Spacer(); Text(HouseholdPlanPresentation.money(item.amountMinor, currency: item.currency, digits: item.currencyFractionDigits)) }
            Text(item.date + " · " + NSLocalizedString("sharedPlan.purpose." + item.purpose.rawValue, comment: "") + " · " + NSLocalizedString("sharedPlan.claim." + item.status.rawValue, comment: "")).font(.footnote).foregroundStyle(ArgusStyle.secondary)
            if item.original != nil { Button("sharedPlan.original") { Task { await model.openOriginal(item) } }.accessibilityIdentifier("sharedPlan.original." + item.id.uuidString).frame(minHeight: 44) }
            if plan.canContribute {
                HStack {
                    if item.canCorrect { Button("household.correct") { model.show(.record(plan, item)) }.accessibilityIdentifier("sharedPlan.correct." + item.id.uuidString).frame(minHeight: 44) }
                    if item.canRelease { Button("sharedPlan.release") { Task { await model.release(item, plan: plan) } }.accessibilityIdentifier("sharedPlan.release." + item.id.uuidString).frame(minHeight: 44) }
                }.disabled(model.pending || model.busy)
            }
        }.padding(.vertical, 8).accessibilityIdentifier("sharedPlan.contribution." + item.id.uuidString)
    }
}

enum HouseholdPlanPresentation {
    static func money(_ minor: String?, plan: HouseholdPlan) -> String { money(minor, currency: plan.definition.common.currency, digits: plan.definition.common.currencyFractionDigits) }
    static func money(_ minor: String?, currency: String, digits: Int) -> String {
        guard let minor else { return currency + " " + NSLocalizedString("household.unknown", comment: "") }
        return currency + " " + AccountPresentation.amount(AccountPresentation.decimal(minor, digits: digits), locale: .current)
    }
    static func decimal(_ minor: String, digits: Int) -> String { AccountPresentation.decimal(minor, digits: digits) }
    static func period(_ item: HouseholdPlanResponsibility, plan: HouseholdPlan) -> String {
        if let period = item.period { return period }
        if let date = item.agreedDate { return date }
        if let id = item.occurrenceId { return plan.occurrences.first { $0.id == id }?.date ?? NSLocalizedString("sharedPlan.previousOccurrence", comment: "") }
        return NSLocalizedString("sharedPlan.schedule", comment: "")
    }
}

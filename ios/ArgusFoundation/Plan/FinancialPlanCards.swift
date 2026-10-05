import SwiftUI
import ArgusSession

struct FinancialPlanCards: View {
    @ObservedObject var model: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    let projection: FinancialPlanProjection
    let create: () -> Void
    var bottomSpace: CGFloat = 90
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var items: [FinancialPlanCardItem] { FinancialPlanCardItem.items(in: projection).filter { !$0.archived } }

    var body: some View {
        CuadraoPlanCollection(spanish: spanish, isEmpty: items.isEmpty,
            canCreate: loop.pendingConfirmation == nil && !model.saving, create: create) {
            ForEach(items) { item in
                Button { Task { await item.open(in: loop) } } label: {
                    CuadraoPlanCard(display: item.display(locale: locale))
                }.buttonStyle(.plain).accessibilityIdentifier("plan.card." + item.id)
            }
        } archives: {
            CuadraoPlanArchiveLink(spanish: spanish) {
                FinancialArchivedPlans(model: model, loop: loop, bottomSpace: bottomSpace)
            }
        }
    }
}

private struct FinancialArchivedPlans: View {
    @ObservedObject var model: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    let bottomSpace: CGFloat
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var items: [FinancialPlanCardItem] {
        model.projection.map(FinancialPlanCardItem.items)?.filter(\.archived) ?? []
    }

    var body: some View {
        List {
            if items.isEmpty {
                ContentUnavailableView(spanish ? "Nada archivado" : "Nothing archived", systemImage: "archivebox",
                    description: Text(spanish ? "Tus planes pueden descansar aquí. Siempre podrás retomarlos." : "Plans can rest here. You can always pick them back up."))
                    .listRowSeparator(.hidden)
            }
            ForEach(items) { item in
                Button { Task { await item.open(in: loop) } } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.name)
                            Text("context.personal").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption2).accessibilityHidden(true)
                    }.frame(minHeight: 48).contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityIdentifier("plan.archived." + item.id)
            }
        }.navigationTitle(spanish ? "Archivados" : "Archived").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar).safeAreaPadding(.bottom, bottomSpace)
    }
}

private enum FinancialPlanCardItem: Identifiable {
    case goal(FinancialGoalProgress)
    case budget(FinancialBudgetProgress)
    case debt(FinancialDebtProgress)

    static func items(in projection: FinancialPlanProjection) -> [Self] {
        (projection.goals ?? []).map(Self.goal) + projection.budgets.map(Self.budget) + (projection.debts ?? []).map(Self.debt)
    }
    var id: String {
        switch self {
        case .goal(let item): "goal." + item.id.uuidString
        case .budget(let item): "budget." + item.id.uuidString
        case .debt(let item): "debt." + item.id.uuidString
        }
    }
    var name: String {
        switch self {
        case .goal(let item): item.goal.name
        case .budget(let item): item.budget.name
        case .debt(let item): item.debt.name
        }
    }
    var archived: Bool {
        switch self {
        case .goal(let item): item.goal.archived
        case .budget(let item): item.budget.archived
        case .debt(let item): item.debt.archived
        }
    }
    @MainActor func open(in loop: FinancialLoopModel) async {
        switch self {
        case .goal(let item): await loop.goals.open(item.id, origin: .planOverview)
        case .budget(let item): await loop.budgets.open(item.id, origin: .planOverview)
        case .debt(let item): await loop.debts.open(item.id, origin: .planOverview)
        }
    }
    func display(locale: Locale) -> CuadraoPlanCardDisplay {
        let personal = NSLocalizedString("context.personal", comment: "")
        func money(_ minor: String?, _ currency: String, _ digits: Int) -> String {
            minor.map { PlanPresentation.money($0, currency: currency, digits: digits, locale: locale) }
                ?? currency + " · " + NSLocalizedString("accounts.unknown", comment: "")
        }
        switch self {
        case .goal(let progress):
            let currency = progress.goal.currency, digits = progress.goal.currencyFractionDigits
            return .init(name: name, space: personal, look: .coast,
                amount: money(progress.supportedMinor, currency, digits), annotation: NSLocalizedString("goal.supported", comment: ""),
                progress: progress.meterFraction,
                detail: NSLocalizedString("goal.target", comment: "") + ": " + money(String(progress.goal.targetMinor), currency, digits),
                notice: NSLocalizedString("goal.state." + progress.state, comment: ""))
        case .budget(let progress):
            let currency = progress.budget.currency, digits = progress.budget.currencyFractionDigits
            return .init(name: name, space: personal, look: .sunshine,
                amount: money(progress.spentMinor, currency, digits),
                annotation: NSLocalizedString(progress.isOverBudget ? "budget.over" : "budget.remaining", comment: "") + " " +
                    money(progress.isOverBudget ? progress.overBudgetMinor : progress.remainingMinor, currency, digits),
                progress: progress.meterFraction,
                detail: NSLocalizedString("budget.of", comment: "") + " " + money(String(progress.budget.limitMinor), currency, digits) + " · " + progress.budget.month)
        case .debt(let progress):
            let credit = progress.balance.creditMinor != nil && progress.balance.creditMinor != 0
            return .init(name: name, space: personal, look: .bloom,
                amount: money((credit ? progress.balance.creditMinor : progress.balance.amountMinor).map(String.init), progress.debt.currency, progress.debt.currencyFractionDigits),
                annotation: NSLocalizedString(credit ? "debt.credit" : "debt.recorded", comment: ""),
                detail: NSLocalizedString("debt.state." + progress.state, comment: ""))
        }
    }
}

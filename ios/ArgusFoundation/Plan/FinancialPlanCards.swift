import SwiftUI
import ArgusSession

struct FinancialPlanCards: View {
    @ObservedObject var model: FinancialPlanModel
    @ObservedObject var loop: FinancialLoopModel
    let projection: FinancialPlanProjection
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private var personal: String { NSLocalizedString("context.personal", comment: "") }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(spanish ? "Tus planes" : "Your plans").font(CuadraoTypography.section)
            ForEach((projection.goals ?? []).filter { !$0.goal.archived }) { progress in
                Button { Task { await loop.goals.open(progress.id, origin: .planOverview) } } label: {
                    CuadraoPlanCard(display: goal(progress))
                }.buttonStyle(.plain).accessibilityIdentifier("plan.card.goal." + progress.id.uuidString)
            }
            ForEach(projection.budgets.filter { !$0.budget.archived }) { progress in
                Button { Task { await loop.budgets.open(progress.id, origin: .planOverview) } } label: {
                    CuadraoPlanCard(display: budget(progress))
                }.buttonStyle(.plain).accessibilityIdentifier("plan.card.budget." + progress.id.uuidString)
            }
            ForEach((projection.debts ?? []).filter { !$0.debt.archived }) { progress in
                Button { Task { await loop.debts.open(progress.id, origin: .planOverview) } } label: {
                    CuadraoPlanCard(display: debt(progress))
                }.buttonStyle(.plain).accessibilityIdentifier("plan.card.debt." + progress.id.uuidString)
            }
            if projection.budgets.allSatisfy({ $0.budget.archived }),
               (projection.goals ?? []).allSatisfy({ $0.goal.archived }), (projection.debts ?? []).allSatisfy({ $0.debt.archived }) {
                VStack(alignment: .leading, spacing: 12) {
                    PlanLandscape(look: .sunshine).frame(height: 135)
                    Text(spanish ? "¿Qué tienes en mente?" : "What do you have in mind?").font(CuadraoTypography.section)
                    Text("goal.empty").font(.subheadline).foregroundStyle(.secondary)
                    PlanPrimaryButton(title: NSLocalizedString("goal.add", comment: ""), symbol: "plus") { loop.goals.create() }
                        .disabled(loop.pendingConfirmation != nil || model.saving)
                }.padding(24).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 26))
            }
        }
    }

    private func goal(_ progress: FinancialGoalProgress) -> CuadraoPlanCardDisplay {
        let currency = progress.goal.currency, digits = progress.goal.currencyFractionDigits
        return .init(name: progress.goal.name, space: personal, look: .coast,
            amount: money(progress.supportedMinor, currency, digits), annotation: NSLocalizedString("goal.supported", comment: ""),
            progress: progress.meterFraction,
            detail: NSLocalizedString("goal.target", comment: "") + ": " + money(String(progress.goal.targetMinor), currency, digits),
            notice: NSLocalizedString("goal.state." + progress.state, comment: ""))
    }
    private func budget(_ progress: FinancialBudgetProgress) -> CuadraoPlanCardDisplay {
        let currency = progress.budget.currency, digits = progress.budget.currencyFractionDigits
        return .init(name: progress.budget.name, space: personal, look: .bloom,
            amount: money(progress.spentMinor, currency, digits),
            annotation: NSLocalizedString(progress.isOverBudget ? "budget.over" : "budget.remaining", comment: "") + " " +
                money(progress.isOverBudget ? progress.overBudgetMinor : progress.remainingMinor, currency, digits),
            progress: progress.meterFraction,
            detail: NSLocalizedString("budget.of", comment: "") + " " + money(String(progress.budget.limitMinor), currency, digits) + " · " + progress.budget.month)
    }
    private func debt(_ progress: FinancialDebtProgress) -> CuadraoPlanCardDisplay {
        let credit = progress.balance.creditMinor != nil && progress.balance.creditMinor != 0
        return .init(name: progress.debt.name, space: personal, look: .clay,
            amount: money((credit ? progress.balance.creditMinor : progress.balance.amountMinor).map(String.init), progress.debt.currency, progress.debt.currencyFractionDigits),
            annotation: NSLocalizedString(credit ? "debt.credit" : "debt.recorded", comment: ""),
            detail: NSLocalizedString("debt.state." + progress.state, comment: ""))
    }
    private func money(_ minor: String?, _ currency: String, _ digits: Int) -> String {
        minor.map { PlanPresentation.money($0, currency: currency, digits: digits, locale: locale) }
            ?? currency + " · " + NSLocalizedString("accounts.unknown", comment: "")
    }
}

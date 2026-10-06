import SwiftUI
import ArgusSession

struct FinancialComingUpView: View {
    @ObservedObject var model: FinancialPlanModel
    let viewPlan: () -> Void
    @State private var expanded = false
    @EnvironmentObject private var auth: ProfileAuthModel
    @Environment(\.locale) private var locale
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private static let compactCount = 4

    var body: some View {
        CuadraoUpcomingSection(spanish: spanish, viewPlan: viewPlan) {
            if let projection = model.homeProjection {
                let planned = projection.occurrences.filter { $0.status != .fulfilled }
                ForEach(Array(planned.prefix(expanded ? planned.count : Self.compactCount))) { occurrence in
                    Button { Task { await model.open(occurrence) } } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            CuadraoFeedRow(title: occurrence.title,
                                detail: PlanPresentation.dateLabel(occurrence.dueDate, locale: locale) + " · "
                                    + NSLocalizedString("plan.status." + occurrence.status.rawValue, comment: ""),
                                amount: (occurrence.kind == .income ? "+" : "")
                                    + AccountPresentation.amount(occurrence.amount, locale: locale) + " " + occurrence.currency,
                                icon: occurrence.kind == .income ? "arrow.down.left" : "calendar")
                            if occurrence.overdue { Text("plan.overdue").font(.caption).foregroundStyle(WelcomePalette.owedNegative) }
                            if let reason = occurrence.exclusionReason {
                                Text(LocalizedStringKey("plan.exclusion." + reason)).font(.caption).foregroundStyle(.secondary)
                            }
                        }.accessibilityElement(children: .combine)
                    }.buttonStyle(.plain).disabled(model.saving).accessibilityIdentifier("home.upcoming." + occurrence.id)
                }
                if planned.count > Self.compactCount {
                    Button(expanded ? "plan.showLess" : "plan.showMore") { expanded.toggle() }
                        .frame(minHeight: 44).accessibilityIdentifier("home.upcoming.more")
                }
                if planned.isEmpty {
                    Text(spanish ? "No tienes pagos previstos en este período." : "No expected payments in this period.")
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text(verbatim: NSLocalizedString("plan.until.label", comment: "") + " " + PlanPresentation.dateLabel(projection.endDate, locale: locale))
                        .accessibilityIdentifier("home.upcoming.until")
                    ForEach(CurrencyPresentation.ordered(projection.currencies, primary: auth.profile?.currency, currency: { $0.currency })) { currency in
                        Text(projection.accounts.filter { currency.accountIds.contains($0.id) }.map {
                            $0.nickname ?? NSLocalizedString("accounts.type." + $0.type, comment: "")
                        }.joined(separator: " · "))
                        if let ending = currency.endingMinor {
                            HStack {
                                Text("plan.projectedBalance")
                                Spacer(minLength: 8)
                                Text(verbatim: PlanPresentation.money(ending, currency: currency.currency, digits: currency.currencyFractionDigits, locale: locale))
                                    .monospacedDigit().accessibilityIdentifier("home.projected." + currency.currency)
                            }
                        } else {
                            Text(currency.currency + " · " + NSLocalizedString("plan.unknown", comment: ""))
                        }
                        if let asOf = currency.asOf {
                            Text(NSLocalizedString("plan.asOf", comment: "") + " "
                                + AccountPresentation.date(asOf, zone: TimeZone.current.identifier, locale: locale))
                        }
                        if currency.firstShortfallDate != nil { Text("plan.shortfall").foregroundStyle(WelcomePalette.owedNegative) }
                    }
                    if projection.selection.accountIds.isEmpty { Text("plan.empty") }
                    Text("plan.home.disclosure")
                }.font(CuadraoTypography.caption).foregroundStyle(.secondary)
            } else if model.loading { ProgressView("accounts.loading") }
            else if let error = model.homeErrorKey {
                Text(LocalizedStringKey(error)).foregroundStyle(.secondary)
                Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44)
            }
        }
    }
}

import SwiftUI
import ArgusSession

/// Home's Upcoming: the server-default window from `homeProjection`, independent
/// of the horizon Plan explores. Planned occurrences open the same occurrence
/// view as Plan; a due date never records money.
struct FinancialComingUpView: View {
    @ObservedObject var model: FinancialPlanModel
    let viewPlan: () -> Void
    @State private var expanded = false
    @Environment(\.locale) private var locale
    private static let compactCount = 4

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("home.coming").font(ArgusStyle.display(23)).accessibilityIdentifier("home.comingUp")
                Spacer()
                Button("home.viewplan", action: viewPlan).font(ArgusStyle.body(12, relativeTo: .caption))
                    .frame(minHeight: 44).accessibilityIdentifier("home.viewPlan")
            }
            if let projection = model.homeProjection {
                Text(verbatim: NSLocalizedString("plan.until.label", comment: "") + " " + PlanPresentation.dateLabel(projection.endDate, locale: locale))
                    .font(ArgusStyle.body(13, relativeTo: .subheadline)).accessibilityIdentifier("home.upcoming.until")
                ForEach(projection.currencies) { currency in
                    FinancialForecastSummary(currency: currency, identifier: "home.projected.")
                    Text(projection.accounts.filter { currency.accountIds.contains($0.id) }.map {
                        $0.nickname ?? NSLocalizedString("accounts.type." + $0.type, comment: "")
                    }.joined(separator: " · ")).font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                    if currency.firstShortfallDate != nil { Text("plan.shortfall").font(ArgusStyle.body(13, relativeTo: .subheadline)) }
                }
                let planned = projection.occurrences.filter { $0.status != .fulfilled }
                ForEach(Array(planned.prefix(expanded ? planned.count : Self.compactCount))) { occurrence in
                    Button { Task { await model.open(occurrence) } } label: { FinancialOccurrenceRow(occurrence: occurrence) }
                        .buttonStyle(.plain).disabled(model.saving).accessibilityIdentifier("home.upcoming." + occurrence.id)
                }
                if planned.count > Self.compactCount {
                    Button(expanded ? "plan.showLess" : "plan.showMore") { expanded.toggle() }
                        .frame(minHeight: 44).accessibilityIdentifier("home.upcoming.more")
                }
                if !projection.hasExpectations || projection.selection.accountIds.isEmpty { Text("plan.empty").foregroundStyle(ArgusStyle.secondary) }
                Text("plan.home.disclosure").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            } else if model.loading { ProgressView("accounts.loading") }
            else if let error = model.homeErrorKey {
                Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                Button("accounts.retry") { Task { await model.refresh() } }.frame(minHeight: 44)
            }
        }
    }
}

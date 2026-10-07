import SwiftUI
import ArgusSession

struct ConnectedCuadraoMovementRow: View {
    let activity: FinancialActivity
    let account: FinancialAccount
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            CuadraoFeedRow(title: activity.note.flatMap { $0.isEmpty ? nil : $0 }
                ?? NSLocalizedString("loop.kind." + activity.kind, comment: ""),
                detail: (account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: ""))
                    + " · " + AccountPresentation.date(activity.occurredAt, zone: activity.timeZone, locale: locale),
                amount: FinancialActivityPresentation.sign(for: activity.balanceMovementMinor) + AccountPresentation.amount(activity.amount, locale: locale) + " " + account.currency,
                icon: FinancialActivityPresentation.symbol(for: activity.kind))
            if activity.active == false {
                Text("loop.activity.moved").font(.caption).foregroundStyle(.secondary)
                    .accessibilityIdentifier("activity.moved")
            }
        }.accessibilityElement(children: .combine)
    }
}

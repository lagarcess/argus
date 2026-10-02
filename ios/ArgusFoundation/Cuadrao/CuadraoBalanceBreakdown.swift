import SwiftUI

struct CuadraoBalanceBreakdown: View {
    let period: CanvasBalancePeriod
    let currency: String
    let spanish: Bool
    @Environment(\.dynamicTypeSize) private var typeSize
    private func money(_ value: Decimal) -> String { CanvasMoney.format(value, currency: currency) }
    private func signed(_ value: Decimal) -> String { (value > 0 ? "+" : "") + money(value) }
    private func date(_ value: Date) -> String {
        value.formatted(.dateTime.day().month(.abbreviated).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(period.change == nil ? (spanish ? "Tu punto de partida" : "Your starting point") : (spanish ? "Qué cambió" : "What changed"))
                .font(CuadraoTypography.section).accessibilityAddTraits(.isHeader)
            if let opening = period.opening, let closing = period.closing {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 20) {
                        snapshot(opening, title: spanish ? "Inicio registrado" : "Recorded opening")
                        Image(systemName: "arrow.right").font(CuadraoTypography.supporting).foregroundStyle(.secondary).accessibilityHidden(true)
                        snapshot(closing, title: spanish ? "Último balance" : "Latest balance")
                    }
                    VStack(alignment: .leading, spacing: 16) {
                        snapshot(opening, title: spanish ? "Inicio registrado" : "Recorded opening")
                        snapshot(closing, title: spanish ? "Último balance" : "Latest balance")
                    }
                }.accessibilityIdentifier("home-balance-comparison")
            } else {
                Text(spanish ? "Con otro balance registrado podrás ver cuánto cambió cada cuenta." : "Another recorded balance will show how much each account changed.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            }
            VStack(spacing: 0) {
                ForEach(period.changes) { row in
                    NavigationLink(value: row.id) {
                        HStack(spacing: 12) {
                            if typeSize.isAccessibilitySize {
                                VStack(alignment: .leading, spacing: 8) {
                                    accountLabel(row)
                                    accountValue(row, alignment: .leading)
                                }
                                Spacer(minLength: 0)
                            } else {
                                accountLabel(row)
                                Spacer(minLength: 8)
                                accountValue(row, alignment: .trailing)
                            }
                            Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary)
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 14).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("home-balance-change-" + row.id.uuidString)
                }
            }
            if let change = period.change {
                Divider()
                HStack {
                    Text(spanish ? "Cambio neto" : "Net change").font(CuadraoTypography.supporting)
                    Spacer(minLength: 12)
                    Text(signed(change)).font(CuadraoTypography.rowAmount).accessibilityIdentifier("home-balance-net-change")
                }
            }
            if period.isPartial {
                Text(spanish ? "El total incluye solo las cuentas con balance conocido." : "The total includes only accounts with known balances.")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }.padding(.top, 20).accessibilityElement(children: .contain).accessibilityIdentifier("home-balance-breakdown")
    }
    private func snapshot(_ point: CanvasBalancePoint, title: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(CuadraoTypography.caption).foregroundStyle(.secondary)
            Text(money(point.balance)).font(CuadraoTypography.secondaryAmount)
            Text(date(point.date)).font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }.fixedSize(horizontal: false, vertical: true)
    }
    private func accountLabel(_ row: CanvasBalanceChange) -> some View {
        HStack(spacing: 10) {
            CanvasAccountIcon(kind: row.account.kind)
            Text(row.account.displayName(spanish)).font(CuadraoTypography.supporting)
        }
    }
    private func accountValue(_ row: CanvasBalanceChange, alignment: HorizontalAlignment) -> some View {
        VStack(alignment: alignment, spacing: 4) {
            Text(row.change.map(signed) ?? row.closing.map(money) ?? "—").font(CuadraoTypography.rowAmount)
            if let change = row.change {
                Text(change == 0 ? (spanish ? "Sin cambio" : "Unchanged") : change > 0 ? (spanish ? "Suma al balance" : "Adds to balance") : (spanish ? "Resta al balance" : "Reduces balance"))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            } else if row.closing == nil {
                Text(spanish ? "Sin balance" : "No balance").font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }
    }
}

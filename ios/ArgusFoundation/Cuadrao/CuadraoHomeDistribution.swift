import SwiftUI

/// Every percentage uses the same positive-assets total, including account rows.
struct CuadraoHomeDistribution: View {
    let accounts: [CanvasAccount]
    let currency: String
    let spanish: Bool
    var controls: CuadraoInsightControls?
    var historical = false
    var asOf: Date?
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var selectedKind: CanvasAccountKind?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private var known: [CanvasAccount] { accounts.filter { $0.balance != nil } }
    private func value(_ account: CanvasAccount) -> Decimal {
        CanvasBalanceHistory.contribution(account.balance ?? 0, account: account)
    }
    private var positive: [CanvasAccount] { known.filter { value($0) > 0 } }
    private var deductions: [CanvasAccount] { known.filter { value($0) < 0 } }
    private var total: Decimal { amount(positive) }
    private var kinds: [CanvasAccountKind] { CanvasAccountKind.allCases.filter { kind in positive.contains { $0.kind == kind } } }
    private var palette: [Color] { [WelcomePalette.sunshine, WelcomePalette.pine, WelcomePalette.clay, WelcomePalette.overlap, WelcomePalette.bloom, WelcomePalette.sage, WelcomePalette.clay.opacity(0.7), WelcomePalette.pine.opacity(0.65), WelcomePalette.ink.opacity(0.5)] }
    private func color(_ kind: CanvasAccountKind) -> Color { palette[CanvasAccountKind.allCases.firstIndex(of: kind)!] }
    private func rows(_ kind: CanvasAccountKind) -> [CanvasAccount] { positive.filter { $0.kind == kind } }
    private func amount(_ rows: [CanvasAccount]) -> Decimal { rows.reduce(0) { $0 + value($1) } }
    private func fraction(_ amount: Decimal) -> Double { total > 0 ? NSDecimalNumber(decimal: amount / total).doubleValue : 0 }
    private func percent(_ amount: Decimal) -> String {
        fraction(amount).formatted(.percent.precision(.fractionLength(1)).locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
    }
    private func select(_ kind: CanvasAccountKind?) {
        withAnimation(reduceMotion ? .easeInOut(duration: 0.15) : .spring(response: 0.42, dampingFraction: 0.85)) {
            selectedKind = selectedKind == kind ? nil : kind
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 8) {
                Text(asOf.map { (spanish ? "Balance neto · " : "Net balance · ") + $0.formatted(.dateTime.day().month(.abbreviated).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US"))) } ?? (historical ? (spanish ? "Sin balances en este período" : "No balances in this period") : (spanish ? "Balance neto · Hoy" : "Net balance · Today")))
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(currency).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    Text(known.isEmpty ? "—" : CanvasMoney.format(total + amount(deductions), currency: currency))
                        .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                        .accessibilityIdentifier("home-distribution-total")
                }
                if accounts.count != known.count {
                    Text(spanish ? "Faltan balances por registrar" : "Some balances are missing")
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
            }
            if let controls { controls }
            if !positive.isEmpty {
                HStack {
                    Text(spanish ? "Distribución de activos" : "Asset allocation")
                    Spacer()
                    Text(CanvasMoney.format(total, currency: currency)).font(CuadraoTypography.rowAmount)
                }.font(CuadraoTypography.supporting)
                distributionBar
                HStack(spacing: 8) {
                    Button { select(nil) } label: {
                        Text(spanish ? "Todo" : "All").frame(minHeight: 44).contentShape(Rectangle())
                    }
                        .foregroundStyle(selectedKind == nil ? WelcomePalette.ink : .secondary)
                        .accessibilityIdentifier("home-distribution-all")
                    if let selectedKind {
                        Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary)
                        Text(selectedKind.title(spanish)).foregroundStyle(color(selectedKind))
                    }
                    Spacer()
                }.font(CuadraoTypography.supporting).frame(minHeight: 44)
                VStack(spacing: 0) {
                    ForEach(kinds) { kind in
                        categoryRow(kind)
                    }
                }
            } else {
                Text(spanish ? "Tus balances positivos aparecerán aquí." : "Your positive balances will appear here.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary).padding(.vertical, 32)
            }
            if !deductions.isEmpty {
                Divider()
                DisclosureGroup {
                    ForEach(deductions) { account in accountRow(account, showPercent: false) }
                } label: {
                    HStack {
                        Text(spanish ? "Por descontar" : "Deductions")
                        Spacer()
                        Text(CanvasMoney.format(-amount(deductions), currency: currency)).font(CuadraoTypography.rowAmount)
                    }.font(CuadraoTypography.supporting).frame(minHeight: 44)
                }
                HStack {
                    Text(spanish ? "Balance neto" : "Net balance")
                    Spacer()
                    Text(CanvasMoney.format(total + amount(deductions), currency: currency)).font(CuadraoTypography.rowAmount)
                }.font(CuadraoTypography.supporting)
            }
        }.sensoryFeedback(.selection, trigger: selectedKind)
            .onChange(of: kinds) { _, available in
                if let selectedKind, !available.contains(selectedKind) { self.selectedKind = nil }
            }
    }
    private var distributionBar: some View {
        CuadraoAllocationBar(segments: kinds.map {
            CuadraoAllocationSegment(id: $0.rawValue, title: $0.title(spanish), fraction: fraction(amount(rows($0))), color: color($0))
        }, selection: Binding(get: { selectedKind?.rawValue }, set: { selectedKind = $0.flatMap(CanvasAccountKind.init(rawValue:)) }),
            identifier: "home-distribution-segment-")
    }
    private func categoryRow(_ kind: CanvasAccountKind) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button { select(kind) } label: {
                VStack(spacing: 12) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 6) {
                                Text(kind.title(spanish)).font(CuadraoTypography.supporting)
                                Image(systemName: selectedKind == kind ? "chevron.up" : "chevron.down").font(.caption2).foregroundStyle(.secondary)
                            }
                            Text(spanish ? "\(rows(kind).count) \(rows(kind).count == 1 ? "cuenta" : "cuentas")" : "\(rows(kind).count) \(rows(kind).count == 1 ? "account" : "accounts")")
                                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 8)
                        VStack(alignment: .trailing, spacing: 6) {
                            Text(percent(amount(rows(kind)))).font(CuadraoTypography.rowAmount)
                            Text(CanvasMoney.format(amount(rows(kind)), currency: currency)).font(CuadraoTypography.rowAmount).foregroundStyle(.secondary)
                        }
                    }
                    GeometryReader { proxy in
                        Rectangle().fill(WelcomePalette.ink.opacity(0.04))
                        Rectangle().fill(color(kind)).frame(width: max(0, proxy.size.width) * fraction(amount(rows(kind))))
                    }.frame(height: 3).accessibilityHidden(true)
                }.padding(.vertical, 18).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityIdentifier("home-distribution-" + kind.rawValue)
                .accessibilityValue(selectedKind == kind ? (spanish ? "Expandido" : "Expanded") : (spanish ? "Contraído" : "Collapsed"))
            if selectedKind == kind {
                ForEach(rows(kind)) { account in accountRow(account, showPercent: true) }
            }
        }
    }
    private func accountRow(_ account: CanvasAccount, showPercent: Bool) -> some View {
        NavigationLink(value: account.id) {
            HStack(alignment: .firstTextBaseline) {
                Text(account.displayName(spanish)).font(CuadraoTypography.supporting)
                Spacer(minLength: 12)
                VStack(alignment: .trailing, spacing: 5) {
                    if showPercent { Text(percent(value(account))).font(CuadraoTypography.rowAmount) }
                    Text(CanvasMoney.format(value(account), currency: currency)).font(CuadraoTypography.rowAmount).foregroundStyle(.secondary)
                }
                Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary)
            }.padding(.vertical, 15).padding(.leading, 12).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("home-distribution-account-" + account.id.uuidString)
    }

}

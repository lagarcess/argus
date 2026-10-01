import SwiftUI
import Charts

/// Breakdown uses the same signed contributions as the history's current endpoint.
struct CuadraoHomeDistribution: View {
    let accounts: [CanvasAccount]
    let currency: String
    let spanish: Bool
    private var known: [CanvasAccount] { accounts.filter { $0.balance != nil } }
    private func value(_ account: CanvasAccount) -> Decimal {
        CanvasBalanceHistory.contribution(account.balance ?? 0, account: account)
    }
    private var positive: [CanvasAccount] { known.filter { value($0) > 0 } }
    private var deductions: [CanvasAccount] { known.filter { value($0) < 0 } }
    private var kinds: [CanvasAccountKind] { CanvasAccountKind.allCases.filter { kind in positive.contains { $0.kind == kind } } }
    private var palette: [Color] { [.orange, WelcomePalette.pine, .teal, .indigo, .red, .purple, .mint, .brown, .gray] }
    private func color(_ kind: CanvasAccountKind) -> Color { palette[CanvasAccountKind.allCases.firstIndex(of: kind)!] }
    private func amount(_ rows: [CanvasAccount]) -> Decimal { rows.reduce(0) { $0 + value($1) } }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text(currency).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                Text(CanvasBalanceHistory.position(accounts).map { CanvasMoney.format($0, currency: currency) } ?? "—")
                    .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                    .accessibilityIdentifier("home-chart-amount")
            }
            Text(spanish ? "Balance neto registrado · Hoy" : "Recorded net balance · Today")
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            if accounts.count != known.count {
                Text(spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if !positive.isEmpty {
                Chart(kinds) { kind in
                    BarMark(x: .value("Value", NSDecimalNumber(decimal: amount(positive.filter { $0.kind == kind })).doubleValue),
                            y: .value("Assets", ""))
                        .foregroundStyle(color(kind))
                        .accessibilityLabel(kind.title(spanish))
                        .accessibilityValue(CanvasMoney.format(amount(positive.filter { $0.kind == kind }), currency: currency))
                }.chartXAxis(.hidden).chartYAxis(.hidden).frame(height: 24).clipShape(RoundedRectangle(cornerRadius: 5))
                    .padding(.vertical, 8).accessibilityIdentifier("home-distribution-bar")
                ForEach(kinds) { kind in
                    DisclosureGroup {
                        ForEach(positive.filter { $0.kind == kind }) { account in accountRow(account) }
                    } label: {
                        HStack(spacing: 8) {
                            Circle().fill(color(kind)).frame(width: 7, height: 7).accessibilityHidden(true)
                            Text(kind.title(spanish)).font(CuadraoTypography.supporting)
                            Spacer()
                            Text(CanvasMoney.format(amount(positive.filter { $0.kind == kind }), currency: currency))
                                .font(CuadraoTypography.rowAmount)
                        }.frame(minHeight: 44)
                    }.accessibilityIdentifier("home-distribution-" + kind.rawValue)
                }
            } else {
                Text(spanish ? "No hay balances positivos registrados." : "No positive balances recorded.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary).padding(.vertical)
            }
            if !deductions.isEmpty {
                Divider()
                DisclosureGroup {
                    ForEach(deductions) { account in accountRow(account) }
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(spanish ? "Por descontar" : "Deductions").font(CuadraoTypography.supporting)
                        Text(CanvasMoney.format(-amount(deductions), currency: currency)).font(CuadraoTypography.rowAmount)
                    }.frame(minHeight: 44)
                }
                Text(spanish ? "Deudas y balances negativos, separados de tus activos." : "Debts and negative balances, separate from your assets.")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
        }
    }
    private func accountRow(_ account: CanvasAccount) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(account.displayName(spanish)).font(CuadraoTypography.supporting)
            Spacer()
            Text(CanvasMoney.format(value(account), currency: currency)).font(CuadraoTypography.rowAmount)
        }.padding(.vertical, 10).accessibilityElement(children: .combine)
    }
}

struct CuadraoHomeHistorySheet: View {
    let accounts: [CanvasAccount]
    let observations: [CanvasBalanceObservation]
    let currency: String
    let spanish: Bool
    let shared: Bool
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                CuadraoHomeBalanceChart(accounts: accounts, observations: observations, currency: currency,
                    currencies: [currency], spanish: spanish, shared: shared, chooseCurrency: { _ in }, expanded: true)
                    .padding(24)
            }.accessibilityIdentifier("home-history-content").background(WelcomePalette.background)
                .navigationTitle(spanish ? "Tu historia" : "Your history").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(spanish ? "Listo" : "Done") { dismiss() }.accessibilityIdentifier("home-history-done")
                    }
                }
        }.tint(WelcomePalette.pine).presentationDragIndicator(.visible)
    }
}

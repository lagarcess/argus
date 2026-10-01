import SwiftUI

/// Every percentage uses the same positive-assets total, including account rows.
struct CuadraoHomeDistribution: View {
    let accounts: [CanvasAccount]
    let currency: String
    let spanish: Bool
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
    private var palette: [Color] { [.orange, WelcomePalette.pine, .teal, .indigo, .red, .purple, .mint, .brown, .gray] }
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
                Text(spanish ? "Así se reparte lo que tienes" : "How your money is spread")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(currency).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                    Text(known.isEmpty ? "—" : CanvasMoney.format(total, currency: currency))
                        .font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
                }.accessibilityIdentifier("home-distribution-total")
                if accounts.count != known.count {
                    Text(spanish ? "Faltan balances por registrar" : "Some balances are missing")
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
            }
            if !positive.isEmpty {
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
    }
    private var distributionBar: some View {
        GeometryReader { geometry in
            let width = max(0, geometry.size.width - 8)
            HStack(spacing: 0) {
                ForEach(kinds) { kind in
                    let active = selectedKind == nil || selectedKind == kind
                    Button { select(kind) } label: {
                        CuadraoAllocationBlock(color: color(kind), filled: active, exposedSide: kind == kinds.first || selectedKind == kind)
                            .frame(width: width * fraction(amount(rows(kind))), height: 62)
                    }.buttonStyle(.plain)
                        .offset(y: !reduceMotion && selectedKind == kind ? -10 : 0)
                        .opacity(active ? 1 : 0.28)
                        .accessibilityElement(children: .ignore)
                        .accessibilityAddTraits(.isButton)
                        .accessibilityAction { select(kind) }
                        .accessibilityLabel(kind.title(spanish))
                        .accessibilityValue(percent(amount(rows(kind))))
                        .accessibilityIdentifier("home-distribution-segment-" + kind.rawValue)
                }
            }.padding(.top, 22)
        }.frame(height: 104)
    }
    private func categoryRow(_ kind: CanvasAccountKind) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button { select(kind) } label: {
                VStack(spacing: 12) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 6) {
                                Text(kind.title(spanish)).font(CuadraoTypography.section)
                                Image(systemName: selectedKind == kind ? "chevron.up" : "chevron.down").font(.caption2).foregroundStyle(.secondary)
                            }
                            Text(spanish ? "\(rows(kind).count) \(rows(kind).count == 1 ? "cuenta" : "cuentas")" : "\(rows(kind).count) \(rows(kind).count == 1 ? "account" : "accounts")")
                                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 8)
                        VStack(alignment: .trailing, spacing: 6) {
                            Text(percent(amount(rows(kind)))).font(CuadraoTypography.rowAmount)
                            Text(CanvasMoney.format(amount(rows(kind)), currency: currency)).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
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
        HStack(alignment: .firstTextBaseline) {
            Text(account.displayName(spanish)).font(CuadraoTypography.supporting)
            Spacer(minLength: 12)
            VStack(alignment: .trailing, spacing: 5) {
                if showPercent { Text(percent(value(account))).font(CuadraoTypography.rowAmount) }
                Text(CanvasMoney.format(value(account), currency: currency)).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 15).padding(.leading, 12).accessibilityElement(children: .combine)
    }
}

private struct CuadraoAllocationBlock: View {
    let color: Color
    let filled: Bool
    let exposedSide: Bool
    var body: some View {
        Canvas { context, size in
            let depth: CGFloat = 8
            let front = Path(CGRect(x: 0, y: depth, width: size.width, height: size.height - depth))
            let top = Path { path in
                path.move(to: .zero); path.addLine(to: CGPoint(x: size.width, y: 0))
                path.addLine(to: CGPoint(x: size.width + depth, y: depth)); path.addLine(to: CGPoint(x: depth, y: depth)); path.closeSubpath()
            }
            let face = front.offsetBy(dx: depth, dy: 0)
            let side = Path { path in
                path.move(to: .zero); path.addLine(to: CGPoint(x: depth, y: depth))
                path.addLine(to: CGPoint(x: depth, y: size.height)); path.addLine(to: CGPoint(x: 0, y: size.height - depth)); path.closeSubpath()
            }
            context.fill(top, with: .color(color.opacity(filled ? 0.55 : 0.04)))
            if exposedSide { context.fill(side, with: .color(color.opacity(filled ? 0.65 : 0.04))) }
            context.fill(face, with: .color(color.opacity(filled ? 0.8 : 0.03)))
            for path in (exposedSide ? [top, side, face] : [top, face]) { context.stroke(path, with: .color(filled ? .white.opacity(0.65) : color), lineWidth: 0.75) }
        }.accessibilityHidden(true)
    }
}

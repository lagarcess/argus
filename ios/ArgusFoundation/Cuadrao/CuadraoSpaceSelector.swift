import SwiftUI

struct CuadraoSpaceSelector: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let add: () -> Void
    var body: some View {
        HStack(spacing: 4) {
            ScrollViewReader { proxy in
                ScrollView(.horizontal) {
                    HStack(spacing: 24) {
                        ForEach(data.visibleSpaces) { space in
                            Button { data.selectedSpaceID = space.id } label: {
                                Text(space.title(spanish))
                                    .font(.subheadline.weight(data.selectedSpaceID == space.id ? .semibold : .regular))
                                    .foregroundStyle(data.selectedSpaceID == space.id ? Color.primary : Color.secondary)
                                    .frame(minHeight: 44).contentShape(Rectangle())
                            }.buttonStyle(.plain).id(space.id)
                                .accessibilityAddTraits(data.selectedSpaceID == space.id ? [.isSelected] : [])
                                .accessibilityIdentifier("cuadrao-space-" + space.id)
                        }
                    }
                }.scrollIndicators(.hidden)
                    .onChange(of: data.selectedSpaceID) { _, id in proxy.scrollTo(id) }
            }
            Button(action: add) { Image(systemName: "plus").frame(width: 44, height: 44) }
                .accessibilityLabel(spanish ? "Añadir o gestionar espacios" : "Add or manage spaces")
                .accessibilityIdentifier("cuadrao-spaces-add")
        }
    }
}

struct CuadraoHomeOverview: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    private var currencies: [String] { Set(data.active.map(\.currency)).sorted() }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(CuadraoTypography.screen).fixedSize(horizontal: false, vertical: true)
            if !data.active.isEmpty {
                ForEach(currencies, id: \.self) { currency in
                    let accounts = data.active.filter { $0.currency == currency }
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(currency).font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
                        Text(accounts.allSatisfy { $0.balance == nil } ? "—" : CanvasMoney.format(accounts.reduce(Decimal.zero) { total, account in
                            total + (account.balance ?? 0) * (account.kind.isDebt ? -1 : 1)
                                * Decimal(account.kind.isAsset ? account.share : 100) / 100
                        }, currency: currency))
                        .font(CuadraoTypography.amount)
                        .monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                    }
                }
                Text(data.active.contains(where: { $0.balance == nil })
                     ? (spanish ? "Balance parcial · Faltan balances" : "Partial balance · Some balances missing")
                     : (data.selectedSpace.kind == .household
                        ? (spanish ? "Balance de cuentas compartidas" : "Shared account balance")
                        : (spanish ? "Balance registrado" : "Recorded balance")))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if data.selectedSpace.kind == .household {
                Text(spanish ? "Solo lo que comparten." : "Only what you share.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }
    private var title: String {
        if data.selectedSpace.kind == .household { return spanish ? "Lo de ustedes." : "Your shared picture." }
        if data.selectedSpace.kind != .personal { return data.selectedSpace.title(spanish) }
        return data.active.isEmpty ? (spanish ? "Un lugar para\ntus finanzas." : "A place for\nyour finances.")
            : (spanish ? "Tu panorama." : "Your overview.")
    }
}

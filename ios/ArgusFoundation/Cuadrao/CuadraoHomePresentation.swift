import SwiftUI

struct CuadraoHomeLayout<Header: View, Notice: View, Section: View>: View {
    let order: [CuadraoHomeSection]
    let canCustomize: Bool
    let spanish: Bool
    let customize: () -> Void
    @ViewBuilder let header: () -> Header
    @ViewBuilder let notice: () -> Notice
    @ViewBuilder let section: (CuadraoHomeSection) -> Section

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 36) {
                VStack(alignment: .leading, spacing: 18, content: header)
                notice()
                ForEach(order, content: section)
                if canCustomize {
                    Button(action: customize) {
                        Label(spanish ? "Ordenar Inicio" : "Reorder Home", systemImage: "slider.horizontal.3")
                            .font(.subheadline).frame(maxWidth: .infinity, minHeight: 44)
                    }.foregroundStyle(.secondary).accessibilityIdentifier("customize-home")
                }
            }
            .padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 32)
        }
        .safeAreaPadding(.bottom, 80)
        .background(WelcomePalette.background)
    }
}

struct CuadraoHomeGreeting: View {
    let name: String
    let spanish: Bool
    var body: some View {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        VStack(alignment: .leading, spacing: 5) {
            Text((spanish ? "Hola" : "Hello") + (name.isEmpty ? "" : ", " + name))
                .font(.title2.weight(.semibold)).accessibilityIdentifier("home-greeting")
        }
    }
}

struct CuadraoUpdatesButton: View {
    let spanish: Bool
    var unread: Int?
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image("CuadraoNotifications").frame(width: 44, height: 44)
                .overlay(alignment: .topTrailing) {
                    if let unread, unread > 0 {
                        Text(String(unread)).font(.caption2.weight(.medium))
                            .foregroundStyle(WelcomePalette.onAccent).padding(4)
                            .background(WelcomePalette.pine, in: Circle()).accessibilityHidden(true)
                    }
                }
        }
        .accessibilityLabel(spanish ? "Novedades" : "Updates")
        .accessibilityValue(unread.map { spanish ? "\($0) sin leer" : "\($0) unread" } ?? "")
        .accessibilityIdentifier("cuadrao.updates.open")
    }
}

struct CuadraoFeedRow: View {
    let title: String
    let detail: String
    let amount: String
    let icon: String
    @Environment(\.dynamicTypeSize) private var size
    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: icon).font(.body).frame(width: 28).foregroundStyle(.secondary).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(.body)
                Text(detail).font(.caption).foregroundStyle(.secondary)
                if size.isAccessibilitySize { Text(amount).font(CuadraoTypography.rowAmount) }
            }
            Spacer()
            if !size.isAccessibilitySize { Text(amount).font(CuadraoTypography.rowAmount) }
        }.padding(.vertical, 6).contentShape(Rectangle())
    }
}

struct CuadraoUpcomingSection<Content: View>: View {
    let spanish: Bool
    let viewPlan: () -> Void
    @ViewBuilder let content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(spanish ? "Próximamente" : "Coming up")
                    .font(CuadraoTypography.section).accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("home.comingUp")
                Spacer()
                Button(spanish ? "Ver plan" : "View plan", action: viewPlan)
                    .font(.subheadline).frame(minHeight: 44).accessibilityIdentifier("home.viewPlan")
            }
            content()
        }
    }
}

struct CuadraoBalanceAmount: View {
    let amount: String
    let currency: String
    let currencies: [String]
    let spanish: Bool
    var expanded = false
    var amountIdentifier = "home-chart-amount"
    let chooseCurrency: (String) -> Void
    let expand: () -> Void
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        Group {
            if typeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline) {
                        currencyLabel
                        Spacer(minLength: 8)
                        expandButton
                    }
                    amountLabel
                }
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    currencyLabel
                    amountLabel
                    if !expanded { Spacer(minLength: 0) }
                    expandButton
                }
            }
        }.font(CuadraoTypography.supporting)
    }

    @ViewBuilder private var currencyLabel: some View {
        if currencies.count > 1 {
            CuadraoChoiceMenu(title: spanish ? "Moneda" : "Currency",
                selection: Binding(get: { currency }, set: chooseCurrency),
                values: currencies, valueTitle: { $0 })
                .accessibilityIdentifier("home-chart-currency")
        } else { Text(currency).foregroundStyle(.secondary) }
    }

    private var amountLabel: some View {
        Text(amount).font(CuadraoTypography.amount).lineLimit(1).minimumScaleFactor(0.5)
            .accessibilityIdentifier(amountIdentifier)
            .accessibilityLabel(currency + " " + amount)
    }

    @ViewBuilder private var expandButton: some View {
        if !expanded {
            Button(action: expand) {
                Image(systemName: "arrow.up.left.and.arrow.down.right").font(.body)
                    .frame(width: 44, height: 44).contentShape(Rectangle())
            }.buttonStyle(.plain).accessibilityLabel(spanish ? "Explorar balance" : "Explore balance")
                .accessibilityIdentifier("home-history-expand")
        }
    }
}

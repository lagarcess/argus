import SwiftUI

enum AppDestination: String, CaseIterable, Identifiable {
    case home, accounts, argus, plan, search
    var id: String { rawValue }
    var title: LocalizedStringKey { LocalizedStringKey("destination." + rawValue) }
    var symbol: String {
        switch self {
        case .home: "house"
        case .accounts: "creditcard"
        case .argus: ""
        case .plan: "target"
        case .search: "magnifyingglass"
        }
    }
}

enum FoundationSheet: String, Identifiable {
    case profile, updates, recents, temporary, sample
    var id: String { rawValue }
    var title: LocalizedStringKey { LocalizedStringKey("sheet." + rawValue) }
}

struct FoundationShell: View {
    @Binding var appearance: AppearancePreference
    @State private var destination: AppDestination = .home
    @State private var sheet: FoundationSheet?

    var body: some View {
        VStack(spacing: 0) {
            header
            ZStack {
                ForEach(AppDestination.allCases) { tab in
                    destinationView(tab)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .opacity(destination == tab ? 1 : 0)
                        .allowsHitTesting(destination == tab)
                        .accessibilityIdentifier("screen.\(tab.rawValue)")
                        .accessibilityHidden(destination != tab)
                }
            }
        }
        .background(ArgusStyle.background.ignoresSafeArea())
        .safeAreaInset(edge: .bottom, spacing: 0) {
            FloatingNavigation(selection: $destination)
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 8)
        }
        .sheet(item: $sheet) { selected in
            FoundationSheetView(sheet: selected, appearance: $appearance)
                .preferredColorScheme(appearance.colorScheme)
                .tint(ArgusStyle.ink)
                .foregroundStyle(ArgusStyle.ink)
        }
    }

    private var header: some View {
        HStack(spacing: 4) {
            if destination == .argus {
                IconButton(title: "sheet.recents", symbol: "clock.arrow.circlepath", identifier: "header.recents") {
                    sheet = .recents
                }
                Spacer()
                IconButton(title: "sheet.temporary", symbol: "bubble.left.and.text.bubble.right", identifier: "header.temporary") {
                    sheet = .temporary
                }
            } else {
                Group {
                    if destination == .home {
                        Text(verbatim: "argus").font(ArgusStyle.display(29))
                    } else {
                        Text(destination.title).font(ArgusStyle.display(22, relativeTo: .title2))
                    }
                }
                .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                IconButton(title: "sheet.updates", symbol: "bell", identifier: "header.updates") { sheet = .updates }
                IconButton(title: "sheet.profile", symbol: "person", identifier: "header.profile") { sheet = .profile }
            }
        }
        .padding(.leading, destination == .argus ? 12 : 24)
        .padding(.trailing, 12)
        .padding(.vertical, 6)
    }

    @ViewBuilder private func destinationView(_ tab: AppDestination) -> some View {
        switch tab {
        case .home: HomeSampleView(destination: $destination, showSample: { sheet = .sample })
        case .accounts: AccountsSampleView(showSample: { sheet = .sample })
        case .argus: ChatSampleView(showSample: { sheet = .sample })
        case .plan: PlanSampleView()
        case .search: SearchSampleView(destination: $destination)
        }
    }
}

struct FloatingNavigation: View {
    @Binding var selection: AppDestination
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency

    var body: some View {
        HStack(spacing: 2) {
            ForEach(AppDestination.allCases) { destination in
                Button { selection = destination } label: {
                    Group {
                        if destination == .argus {
                            ArgusMark().fill(ArgusStyle.ink).frame(width: 29, height: 29)
                        } else {
                            Image(systemName: selection == .home && destination == .home ? "house.fill" : destination.symbol)
                                .font(.system(size: 21, weight: .regular))
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(selection == destination ? ArgusStyle.ink.opacity(0.08) : .clear, in: Capsule())
                    .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(destination.title)
                .accessibilityIdentifier("tab.\(destination.rawValue)")
                .accessibilityAddTraits(selection == destination ? .isSelected : [])
            }
        }
        .padding(6)
        .background {
            if reduceTransparency {
                Capsule().fill(ArgusStyle.surface)
            } else {
                Capsule().fill(.regularMaterial)
            }
        }
        .overlay(Capsule().strokeBorder(ArgusStyle.ink.opacity(0.12), lineWidth: 0.5))
        .shadow(color: .black.opacity(0.08), radius: 14, y: 5)
        .accessibilityElement(children: .contain)
    }
}

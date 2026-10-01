import SwiftUI
import Observation

// Navigation artwork and destination names have one owner across the canvas.
enum CuadraoTab: Int, CaseIterable, Identifiable {
    case home, plan, assistant, search, profile
    var id: Self { self }

    func title(spanish: Bool) -> String {
        switch self {
        case .home: spanish ? "Inicio" : "Home"
        case .plan: "Plan"
        case .assistant: spanish ? "Asistente" : "Assistant"
        case .search: spanish ? "Buscar" : "Search"
        case .profile: spanish ? "Perfil" : "Profile"
        }
    }

    var symbol: String {
        switch self {
        case .home: "house"
        case .plan: "calendar"
        case .assistant: "sparkle"
        case .search: "magnifyingglass"
        case .profile: "person"
        }
    }

    func image(selected: Bool) -> Image {
        switch self {
        case .home: Image(selected ? "CuadraoHomeSelected" : "CuadraoHomeOutline")
        case .plan: Image("CuadraoPlan")
        case .profile: Image("CuadraoProfile")
        default: Image(systemName: symbol)
        }
    }

    /// Maps onto tip `tab.*` / `header.profile` identifiers (no Accounts tab).
    var tipAccessibilityID: String {
        switch self {
        case .home: "tab.home"
        case .plan: "tab.plan"
        case .assistant: "tab.argus"
        case .search: "tab.search"
        case .profile: "header.profile"
        }
    }
}

struct CuadraoNavigationBar: View {
    @Binding var selection: CuadraoTab
    let compact: Bool
    let spanish: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 0) {
            ForEach(CuadraoTab.allCases) { tab in
                Button { selection = tab } label: {
                    tab.image(selected: selection == tab)
                        .environment(\.symbolVariants, .none)
                        .font(.system(size: 25, weight: .regular))
                        .frame(maxWidth: .infinity)
                        .frame(height: 48)
                        .foregroundStyle(selection == tab ? WelcomePalette.pine : Color.secondary)
                        .background {
                            if selection == tab {
                                Capsule().fill(WelcomePalette.pine.opacity(0.09))
                            }
                        }
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(tab.title(spanish: spanish))
                // Tip-compatible ids keep UITests working; Cuadrao ordinal remains for design evidence.
                .accessibilityIdentifier(tab.tipAccessibilityID)
                .accessibilityAddTraits(selection == tab ? .isSelected : [])
            }
        }
        .padding(4)
        .frame(maxWidth: compact ? 270 : .infinity)
        .modifier(CuadraoNavigationMaterial())
        .animation(reduceMotion ? nil : .easeOut(duration: 0.2), value: compact)
    }
}

private struct CuadraoNavigationMaterial: ViewModifier {
    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(iOS 26.0, *) {
            content.glassEffect(.regular.tint(.white.opacity(0.75)), in: .capsule)
        } else {
            content.background(.regularMaterial, in: Capsule())
                .overlay { Capsule().strokeBorder(.primary.opacity(0.08), lineWidth: 0.5) }
        }
    }
}

// Preserves the approved HTML thresholds; bounce cannot collapse the bar.
// The inset stays the same height in both states, avoiding scroll/layout feedback.
@Observable
final class CuadraoNavigationScroll {
    private(set) var compact = false
    @ObservationIgnored private var lastOffset: CGFloat = 0
    @ObservationIgnored private var travel: CGFloat = 0

    @ObservationIgnored private var interacting = false

    func setInteracting(_ value: Bool) {
        interacting = value
        travel = 0
    }

    func update(_ rawOffset: CGFloat) {
        let offset = max(0, rawOffset)
        let change = offset - lastOffset
        defer { lastOffset = offset }
        guard interacting else { return }
        guard change != 0 else { return }
        travel = (change.sign == travel.sign ? travel : 0) + change
        if offset < 50 || travel < -12 {
            compact = false
        } else if travel > 30 && offset > 100 {
            compact = true
        }
    }
}

struct CuadraoNavigationScrollObserver: ViewModifier {
    let scroll: CuadraoNavigationScroll
    let enabled: Bool

    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(iOS 18.0, *) {
            content.onScrollGeometryChange(for: CGFloat.self) { geometry in
                let maximum = max(0, geometry.contentSize.height + geometry.contentInsets.top
                    + geometry.contentInsets.bottom - geometry.containerSize.height)
                return min(maximum, max(0, geometry.contentOffset.y + geometry.contentInsets.top))
            } action: { _, offset in
                if enabled { scroll.update(offset) }
            }
            .onScrollPhaseChange { _, phase in
                scroll.setInteracting(phase == .interacting)
            }
        } else {
            content
        }
    }
}

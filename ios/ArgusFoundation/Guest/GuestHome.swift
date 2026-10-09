import SwiftUI
import CuadraoBook

/// Home for the on-device book, built from the shared Home layout. It reads the book and nothing else.
struct GuestHome: View {
    @ObservedObject var model: GuestBookModel
    let scroll: CuadraoNavigationScroll
    let active: Bool
    @Environment(\.locale) private var locale

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        NavigationStack {
            CuadraoHomeLayout(order: [.accounts], canCustomize: false, spanish: spanish, customize: {}) {
                CuadraoHomeGreeting(name: "", spanish: spanish)
                Text(spanish ? "Este iPhone" : "This iPhone")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(.secondary).frame(minHeight: 44)
                    .accessibilityIdentifier("guest.home.space")
            } notice: {
                if model.saveFailed {
                    Text(spanish ? "No se pudo guardar en este iPhone. Tus cambios siguen aquí mientras la app esté abierta."
                         : "Couldn't save on this iPhone. Your changes stay here while the app is open.")
                        .font(.footnote).foregroundStyle(.secondary).accessibilityIdentifier("guest.home.saveFailed")
                }
            } section: { _ in
                accountsSection
            }
            .accessibilityIdentifier("screen.home")
            .modifier(CuadraoNavigationScrollObserver(scroll: scroll, enabled: active))
            .background(WelcomePalette.background)
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private var accountsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            CuadraoChartState(title: spanish ? "Empieza con una cuenta." : "Start with one account.",
                detail: spanish ? "Tu banco, tu efectivo o tus ahorros. Tú eliges por dónde empezar."
                    : "Your bank, cash or savings. Choose where to begin.")
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("guest.home.empty")
        }
    }
}

import SwiftUI
import CuadraoBook

/// What the on-device book shows: the shell when the book can be used, or an honest notice when it cannot.
struct GuestRoot: View {
    @ObservedObject var model: GuestBookModel
    @Binding var appearance: AppearancePreference
    let webURL: URL?
    let leave: () -> Void
    let deleteData: () async -> Bool
    @Environment(\.locale) private var locale
    @State private var confirmingDelete = false
    @State private var deleteFailed = false

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        switch model.phase {
        case .loading:
            WelcomePalette.brandPaper.ignoresSafeArea()
        case .ready:
            GuestShell(model: model, appearance: $appearance, webURL: webURL, leave: leave, deleteData: deleteData)
                .preferredColorScheme(appearance.colorScheme)
        case .newerVersion:
            notice(title: spanish ? "Actualiza Cuadrao para abrir este libro." : "Update Cuadrao to open this book.",
                   detail: spanish ? "Este libro se guardó con una versión más nueva de la app. No se cambió nada. Actualiza Cuadrao e inténtalo de nuevo."
                       : "This book was saved by a newer version of the app. Nothing was changed. Update Cuadrao and try again.",
                   identifier: "guest.notice.newer", offersDelete: false)
        case .unreadable:
            notice(title: spanish ? "No se pudo abrir tu libro." : "Your book could not be opened.",
                   detail: spanish ? "El archivo de este iPhone no se pudo leer. Puedes eliminarlo y empezar de nuevo."
                       : "The file on this iPhone could not be read. You can delete it and start again.",
                   identifier: "guest.notice.unreadable", offersDelete: true)
        }
    }

    private func notice(title: String, detail: String, identifier: String, offersDelete: Bool) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            Spacer(minLength: 0)
            RegistrationHeading(title: title, detail: detail)
            RegistrationButton(title: spanish ? "Volver" : "Back", action: leave)
                .accessibilityIdentifier("guest.notice.back")
            if offersDelete {
                Button(role: .destructive) { confirmingDelete = true } label: {
                    Text(spanish ? "Eliminar los datos de este iPhone" : "Delete this iPhone's data")
                        .frame(maxWidth: .infinity, minHeight: 44)
                }.accessibilityIdentifier("guest.notice.delete")
            }
            Spacer(minLength: 0)
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .background(WelcomePalette.brandPaper.ignoresSafeArea())
        .foregroundStyle(WelcomePalette.ink)
        .accessibilityIdentifier(identifier)
        .alert(GuestDeleteCopy.title(spanish), isPresented: $confirmingDelete) {
            Button(spanish ? "Cancelar" : "Cancel", role: .cancel) {}
            Button(GuestDeleteCopy.confirm(spanish), role: .destructive) {
                Task { if await !deleteData() { deleteFailed = true } }
            }.accessibilityIdentifier("guest.delete.confirm")
        } message: { Text(GuestDeleteCopy.message(spanish)) }
        .alert(GuestDeleteCopy.failed(spanish), isPresented: $deleteFailed) {
            Button(spanish ? "Entendido" : "Got it", role: .cancel) {}
        }
    }
}

enum GuestDeleteCopy {
    static func title(_ es: Bool) -> String { es ? "¿Eliminar los datos de este iPhone?" : "Delete this iPhone's data?" }
    static func confirm(_ es: Bool) -> String { es ? "Eliminar" : "Delete" }
    static func message(_ es: Bool) -> String {
        es ? "Se borrarán tus cuentas, movimientos, presupuestos y metas de este iPhone. No se puede deshacer."
            : "Your accounts, activity, budgets and goals on this iPhone will be removed. This can't be undone."
    }
    static func failed(_ es: Bool) -> String { es ? "No se pudieron eliminar los datos. Inténtalo de nuevo." : "The data could not be deleted. Try again." }
}

/// The shared Cuadrao shell filled with the book: the same navigation bar, + tray, scroll folding and tabs,
/// with the assistant slot given to the add action because the book has no assistant.
struct GuestShell: View {
    @ObservedObject var model: GuestBookModel
    @Binding var appearance: AppearancePreference
    let webURL: URL?
    let leave: () -> Void
    let deleteData: () async -> Bool
    @Environment(\.locale) private var locale
    @State private var tab: CuadraoTab = .home
    @State private var navigationScroll = CuadraoNavigationScroll()
    @State private var planScroll = CuadraoNavigationScroll()
    @State private var searchScroll = CuadraoNavigationScroll()
    @State private var profileScroll = CuadraoNavigationScroll()
    @State private var profilePath: [GuestProfileRoute] = []
    @State private var chat = CuadraoChatPreview(spanish: Locale.current.language.languageCode?.identifier == "es", includeExamples: false)

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        CuadraoAppShell(selection: $tab, chat: chat, spanish: spanish, showsNavigation: showsNavigation,
                        compact: scroll(for: tab)?.compact ?? false, avatar: .none, profileName: "",
                        addItems: addItems, hasAssistant: GuestAccessPolicy.hasAssistant) { _ in
            ForEach(CuadraoTab.allCases.filter { $0 != .assistant }) { item in
                content(item)
                    .toolbar(.hidden, for: .tabBar)
                    .tag(item)
            }
        }
        .tint(WelcomePalette.pine)
        .foregroundStyle(WelcomePalette.ink)
        .background(WelcomePalette.background.ignoresSafeArea())
    }

    private var showsNavigation: Bool { tab != .profile || profilePath.isEmpty }

    private var addItems: [CuadraoAddItem] {
        GuestAccessPolicy.addActions(activeAccounts: 0).map { CuadraoAddItem(action: $0) {} }
    }

    private func scroll(for item: CuadraoTab) -> CuadraoNavigationScroll? {
        switch item {
        case .home: navigationScroll
        case .plan: planScroll
        case .search: searchScroll
        case .profile: profileScroll
        case .assistant: nil
        }
    }

    @ViewBuilder private func content(_ item: CuadraoTab) -> some View {
        switch item {
        case .home:
            GuestHome(model: model, scroll: navigationScroll, active: tab == .home)
        case .plan:
            GuestPlaceholderTab(scroll: planScroll, active: tab == .plan,
                title: spanish ? "Lo que viene" : "What's ahead",
                detail: spanish ? "Aquí vivirán tus presupuestos y metas." : "Your budgets and goals will live here.",
                identifier: "guest.plan")
        case .search:
            GuestPlaceholderTab(scroll: searchScroll, active: tab == .search,
                title: spanish ? "Buscar" : "Search",
                detail: spanish ? "Aquí buscarás entre tus cuentas y movimientos." : "Here you will search your accounts and activity.",
                identifier: "guest.search")
        case .profile:
            GuestProfile(model: model, appearance: $appearance, path: $profilePath, webURL: webURL, leave: leave, deleteData: deleteData)
                .modifier(CuadraoNavigationScrollObserver(scroll: profileScroll, enabled: tab == .profile && profilePath.isEmpty))
        case .assistant:
            EmptyView()
        }
    }
}

struct GuestPlaceholderTab: View {
    let scroll: CuadraoNavigationScroll
    let active: Bool
    let title: String
    let detail: String
    let identifier: String

    var body: some View {
        ScrollView {
            CuadraoChartState(title: title, detail: detail)
                .padding(.horizontal, 24).padding(.top, 28).padding(.bottom, 32)
        }
        .safeAreaPadding(.bottom, 80)
        .background(WelcomePalette.background)
        .accessibilityIdentifier(identifier)
        .modifier(CuadraoNavigationScrollObserver(scroll: scroll, enabled: active))
    }
}

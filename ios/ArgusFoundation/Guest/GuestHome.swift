import SwiftUI
import CuadraoBook

/// Home for the on-device book, built from the shared Home layout. It reads the book and nothing else.
struct GuestHome: View {
    @ObservedObject var model: GuestBookModel
    let scroll: CuadraoNavigationScroll
    let active: Bool
    @Binding var path: [UUID]
    @Binding var sheet: GuestSheet?
    @State private var archivedID: UUID?
    @Environment(\.locale) private var locale

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        NavigationStack(path: $path) {
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
                GuestAccountsSection(model: model, spanish: spanish,
                    open: { path.append($0) }, add: { sheet = .account(.create) },
                    edit: { sheet = .account(.edit($0)) }, archive: { sheet = .archive($0) },
                    showArchived: { sheet = .archived })
            }
            .accessibilityIdentifier("screen.home")
            .modifier(CuadraoNavigationScrollObserver(scroll: scroll, enabled: active && path.isEmpty && sheet == nil))
            .background(WelcomePalette.background)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: UUID.self) { id in
                GuestAccountDetail(model: model, id: id, spanish: spanish,
                    edit: { sheet = .account(.edit(id)) },
                    archive: { sheet = .archive(id) },
                    restore: { restore(id) })
            }
        }
        .overlay(alignment: .bottom) {
            if let archivedID, path.isEmpty, model.book.account(archivedID)?.archived == true {
                CuadraoArchivedAccountToast(spanish: spanish, undo: { restore(archivedID) }, close: { self.archivedID = nil })
            }
        }
        .onChange(of: sheet) { previous, current in
            // A confirmed archive arrives as the sheet closing after the book changed.
            if case .archive(let id)? = previous, current == nil, model.book.account(id)?.archived == true {
                path = []
                archivedID = id
            }
        }
    }

    private func restore(_ id: UUID) {
        _ = try? model.apply { try $0.settingArchived(id, false) }
        if archivedID == id { archivedID = nil }
    }
}

/// Every sheet the book's Home and its account detail can open.
enum GuestSheet: Identifiable, Equatable {
    case account(GuestAccountSheet.Mode)
    case archive(UUID)
    case archived

    var id: String {
        switch self {
        case .account(let mode): "account." + mode.id
        case .archive(let id): "archive." + id.uuidString
        case .archived: "archived"
        }
    }
}

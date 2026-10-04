import SwiftUI

struct ReleaseUpdatesInbox: View {
    let state: ReleaseUpdatesState
    let spanish: Bool
    var permission: ReleasePushPermission = .unavailable
    var retry: () -> Void = {}
    var loadMore: () -> Void = {}
    var markRead: (String) -> Void = { _ in }
    var openSource: (ReleaseUpdateDestination) -> Void = { _ in }
    var requestPermission: () -> Void = {}
    var openSettings: () -> Void = {}

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 24) {
                switch state {
                case .unavailable:
                    status(spanish ? "Las novedades aún no están disponibles" : "Updates aren't available yet",
                           detail: spanish ? "Cuando estén disponibles, aquí verás lo que necesita tu atención." : "When available, things that need your attention will appear here.")
                case .loading:
                    ProgressView(spanish ? "Cargando novedades…" : "Loading updates…")
                        .frame(maxWidth: .infinity, minHeight: 160).accessibilityIdentifier("updates-loading")
                case .empty:
                    status(spanish ? "Todo al día" : "You're all caught up",
                           detail: spanish ? "No tienes novedades por revisar." : "You have no updates to review.")
                case .failure:
                    status(spanish ? "No pudimos cargar las novedades" : "Couldn't load updates",
                           detail: spanish ? "Inténtalo de nuevo." : "Please try again.")
                    Button(spanish ? "Reintentar" : "Retry", action: retry).frame(minHeight: 44)
                        .accessibilityIdentifier("updates-retry")
                case .loaded(let items, let more):
                    ForEach(items) { item in
                        NavigationLink {
                            detail(item)
                                .onAppear { if !item.isRead { markRead(item.id) } }
                        } label: { row(item) }
                        .buttonStyle(.plain).accessibilityIdentifier("updates-row-" + item.id)
                    }
                    switch more {
                    case .none: EmptyView()
                    case .loading: ProgressView(spanish ? "Cargando más…" : "Loading more…")
                    case .available, .failure:
                        if more == .failure {
                            Text(spanish ? "No se pudieron cargar más novedades." : "Couldn't load more updates.")
                                .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                        }
                        Button(spanish ? "Más" : "More", action: loadMore).frame(minHeight: 44)
                            .accessibilityIdentifier("updates-load-more")
                    }
                }
                if permission != .unavailable {
                    NavigationLink {
                        ReleaseNotificationPreferences(permission: permission, spanish: spanish,
                            requestPermission: requestPermission, openSettings: openSettings)
                    } label: {
                        Label(spanish ? "Notificaciones" : "Notifications", systemImage: "bell")
                            .font(CuadraoTypography.supporting).frame(minHeight: 44)
                    }.accessibilityIdentifier("updates-notification-preferences")
                }
            }.padding(24)
        }.background(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
            .navigationTitle(spanish ? "Novedades" : "Updates").navigationBarTitleDisplayMode(.inline)
            .accessibilityIdentifier("release-updates-inbox")
    }

    private func status(_ title: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            CuadraoMark()
            Text(title).font(CuadraoTypography.section)
            Text(detail).font(CuadraoTypography.body).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 24)
    }

    private func sourceSafeDetail(_ item: ReleaseUpdateItem) -> String {
        switch item.source {
        case .available: item.kind.detail(spanish: spanish)
        case .unavailable:
            switch item.kind {
            case .ownerHistoryRemoved, .householdClosed: item.kind.detail(spanish: spanish)
            default: spanish ? "El origen ya no está disponible." : "The source is no longer available."
            }
        }
    }

    private func row(_ item: ReleaseUpdateItem) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: item.kind.symbol).font(.title3).foregroundStyle(WelcomePalette.pine)
                .frame(width: 42, height: 42).background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 13))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 7) {
                Text(item.kind.title(spanish: spanish)).font(.body.weight(item.isRead ? .regular : .semibold))
                Text(sourceSafeDetail(item)).font(CuadraoTypography.supporting).foregroundStyle(.secondary).lineLimit(3)
                Text(item.occurredAt.formatted(.dateTime.month(.abbreviated).day().year()
                    .locale(Locale(identifier: spanish ? "es_DO" : "en_US"))))
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            Circle().fill(item.isRead ? Color.clear : WelcomePalette.pine).frame(width: 7, height: 7).padding(.top, 7)
                .accessibilityHidden(true)
        }.padding(.vertical, 8).frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            .accessibilityElement(children: .combine)
            .accessibilityValue(item.isRead ? (spanish ? "Leída" : "Read") : (spanish ? "Sin leer" : "Unread"))
    }

    private func detail(_ item: ReleaseUpdateItem) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text(item.kind.title(spanish: spanish)).font(CuadraoTypography.feature)
                Text(sourceSafeDetail(item)).font(CuadraoTypography.body)
                switch item.source {
                case .available(let destination):
                    Button(spanish ? "Ver origen" : "View source") { openSource(destination) }
                        .font(CuadraoTypography.action).frame(minHeight: 44).accessibilityIdentifier("update-open-source")
                case .unavailable:
                    Text(spanish ? "El origen ya no está disponible." : "The source is no longer available.")
                        .foregroundStyle(.secondary).accessibilityIdentifier("update-source-unavailable")
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
        }.background(WelcomePalette.background).navigationTitle(spanish ? "Novedad" : "Update")
            .navigationBarTitleDisplayMode(.inline)
    }
}

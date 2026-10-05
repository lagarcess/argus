import SwiftUI

public struct ReleaseConnectedSourcesView: View {
    public let sources: [ReleaseConnectedSource]
    public let onDisconnect: (String) -> Void
    public let onRetry: (String) -> Void
    @State private var confirmation: ReleaseConnectedSource?
    @Environment(\.locale) private var locale

    public init(sources: [ReleaseConnectedSource], onDisconnect: @escaping (String) -> Void,
                onRetry: @escaping (String) -> Void) {
        self.sources = sources; self.onDisconnect = onDisconnect; self.onRetry = onRetry
    }

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private func text(_ es: String, _ en: String) -> String { spanish ? es : en }

    public var body: some View {
        List {
            if sources.isEmpty {
                Section {
                    Label(text("No tienes fuentes conectadas", "No connected sources"), systemImage: "link")
                    Text(text("Aquí aparecerán las fuentes que conectes.", "Sources you connect will appear here."))
                        .foregroundStyle(.secondary)
                }
            }
            ForEach(sources) { source in
                Section {
                    Text(source.name).font(CuadraoTypography.action)
                    if !source.detail.isEmpty { Text(source.detail).font(CuadraoTypography.supporting).foregroundStyle(.secondary) }
                    sourceStatus(source)
                }.accessibilityIdentifier("identity.source.\(source.id)")
            }
        }
        .font(CuadraoTypography.body).tint(WelcomePalette.pine)
        .navigationTitle(text("Fuentes conectadas", "Connected sources"))
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(text("¿Desconectar esta fuente?", "Disconnect this source?"),
                            isPresented: Binding(get: { confirmation != nil }, set: { if !$0 { confirmation = nil } }),
                            titleVisibility: .visible, presenting: confirmation) { source in
            Button(text("Desconectar", "Disconnect"), role: .destructive) { onDisconnect(source.id) }
            Button(text("Cancelar", "Cancel"), role: .cancel) { confirmation = nil }
        } message: { source in
            Text(text("Cuadrao dejará de recibir datos de \(source.name). Los registros que ya confirmaste se conservarán.",
                      "Cuadrao will stop receiving data from \(source.name). Records you already confirmed will stay."))
        }
        .accessibilityIdentifier("identity.sources.screen")
    }

    @ViewBuilder private func sourceStatus(_ source: ReleaseConnectedSource) -> some View {
        switch source.state {
        case .connected:
            Button(text("Desconectar", "Disconnect"), role: .destructive) { confirmation = source }
                .accessibilityIdentifier("identity.source.disconnect.\(source.id)")
        case .disconnecting:
            ProgressView(text("Desconectando…", "Disconnecting…"))
        case .pending:
            Label(text("Esperando confirmación", "Waiting for confirmation"), systemImage: "clock")
            Text(text("La fuente todavía no ha confirmado la desconexión.", "This source has not confirmed disconnection yet."))
                .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            retry(source)
        case .failed:
            Label(text("No se pudo desconectar", "Couldn't disconnect"), systemImage: "exclamationmark.circle")
            retry(source)
        case .disconnected:
            Label(text("Desconectada", "Disconnected"), systemImage: "checkmark.circle")
        }
    }

    private func retry(_ source: ReleaseConnectedSource) -> some View {
        Button(text("Volver a intentar", "Try again")) { onRetry(source.id) }
            .accessibilityIdentifier("identity.source.retry.\(source.id)")
    }
}

import SwiftUI

struct CuadraoTemporaryChatSettings: View {
    let store: CuadraoChatPreview
    let spanish: Bool
    let returnToRegular: () -> Void
    private var es: Bool { spanish }

    var body: some View {
        @Bindable var store = store
        VStack(alignment: .leading, spacing: 28) {
            VStack(alignment: .leading, spacing: 18) {
                explanation("clock", es ? "Fuera de tu historial" : "Outside your history",
                    es ? "No aparece en Chats ni en Buscar." : "Does not appear in Chats or Search.")
                if CuadraoFirstRelease.shows(.memory) {
                    explanation("brain", es ? "Sin nuevas memorias" : "No new memories",
                        es ? "Lo que hables aquí no se añade a tus memorias." : "What you discuss here is not added to your memories.")
                }
            }
            Divider()
            VStack(alignment: .leading, spacing: 12) {
                Toggle(es ? "Usar mi contexto" : "Use my context", isOn: $store.useContext)
                    .font(CuadraoTypography.action).disabled(store.contextLocked)
                    .accessibilityIdentifier("temporary-context")
                Text(CuadraoFirstRelease.shows(.memory)
                    ? (es ? "Tus memorias, preferencias de respuesta y registros financieros a los que tienes acceso." : "Your memories, response preferences and financial records you can access.")
                    : (es ? "Tus preferencias de respuesta y registros financieros a los que tienes acceso." : "Your response preferences and financial records you can access."))
                    .font(.subheadline).foregroundStyle(.secondary)
                if store.contextLocked {
                    Label(es ? "La elección queda fija en este chat. Inicia otro chat temporal para cambiarla." : "This choice is fixed for this chat. Start another temporary chat to change it.", systemImage: "lock")
                        .font(.footnote).foregroundStyle(.secondary)
                } else {
                    Text(store.useContext
                        ? (es ? "Se mantienen tus permisos de privacidad y de acceso." : "Your privacy and access permissions still apply.")
                        : (es ? "Solo lo que compartas aquí. Se mantienen el idioma y la accesibilidad de tu dispositivo." : "Only what you share here. Your device language and accessibility settings still apply."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            DisclosureGroup(es ? "¿Qué pasa cuando salgo?" : "What happens when I leave?") {
                VStack(alignment: .leading, spacing: 14) {
                    Text(es ? "Al terminar este chat o ir a otra sección de Cuadrao, se descarta su contenido. Cambiar de app por un momento no lo termina." : "Ending this chat or moving to another section of Cuadrao discards its content. Briefly switching apps does not end it.")
                    Text(es ? "Tu chat anterior y su borrador quedan intactos. Este chat temporal no crea registros financieros." : "Your previous chat and its draft stay intact. This temporary chat does not create financial records.")
                    Text(es ? "Vista previa: no accede a una IA ni a tus datos. La retención y el tratamiento por proveedores aún deben implementarse; no es una garantía de anonimato." : "Preview: no AI or personal data is accessed. Retention and provider handling still need implementation; this is not an anonymity guarantee.")
                }.font(.footnote).foregroundStyle(.secondary).padding(.top, 12)
            }.font(.subheadline)
            Button(action: returnToRegular) {
                Text(es ? "Volver al chat normal" : "Return to regular chat")
                    .font(CuadraoTypography.action).frame(maxWidth: .infinity, minHeight: 48)
            }.accessibilityIdentifier("temporary-return")
        }
    }

    private func explanation(_ symbol: String, _ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: symbol).font(.system(size: 20)).frame(width: 24, height: 26)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(CuadraoTypography.action)
                Text(detail).font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }
}

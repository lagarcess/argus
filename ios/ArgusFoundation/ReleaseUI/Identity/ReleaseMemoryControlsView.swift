import SwiftUI

public struct ReleaseMemoryControlsView: View {
    public let state: ReleaseMemoryState
    public let onSetEnabled: (Bool) -> Void
    public let onReset: () -> Void
    @Environment(\.locale) private var locale
    @State private var confirmingReset = false

    public init(state: ReleaseMemoryState, onSetEnabled: @escaping (Bool) -> Void, onReset: @escaping () -> Void) {
        self.state = state; self.onSetEnabled = onSetEnabled; self.onReset = onReset
    }

    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }
    private func text(_ es: String, _ en: String) -> String { spanish ? es : en }

    public var body: some View {
        List {
            Section {
                Toggle(text("Usar memoria", "Use memory"), isOn: Binding(get: { state.isEnabled }, set: onSetEnabled))
                    .disabled(state.isBusy).accessibilityIdentifier("identity.memory.enabled")
                Text(text("Cuadrao puede recordar lo que tú confirmes para personalizar sus respuestas.",
                          "Cuadrao can remember what you confirm to personalize its responses."))
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                if !state.isEnabled && !state.isBusy {
                    Label(text("Memoria desactivada", "Memory is off"), systemImage: "pause.circle")
                }
            } footer: {
                Text(text("Desactivar la memoria conserva lo guardado. Restablecerla borra todos los recuerdos.",
                          "Turning memory off keeps saved memories. Resetting deletes all memories."))
            }
            Section {
                if state.isBusy { ProgressView(text("Guardando cambios…", "Saving changes…")) }
                if case .failed = state {
                    Label(text("No se pudo completar. Vuelve a intentarlo.", "Couldn't finish. Try again."),
                          systemImage: "exclamationmark.circle")
                }
                if case .resetComplete = state {
                    Label(text("Memoria restablecida", "Memory reset"), systemImage: "checkmark.circle")
                        .accessibilityIdentifier("identity.memory.resetComplete")
                }
                Button(text("Restablecer memoria", "Reset memory"), role: .destructive) { confirmingReset = true }
                    .disabled(state.isBusy).accessibilityIdentifier("identity.memory.reset")
            }
        }
        .font(CuadraoTypography.body).tint(WelcomePalette.pine)
        .navigationTitle(text("Memoria", "Memory"))
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(text("¿Borrar todos los recuerdos?", "Delete all memories?"),
                            isPresented: $confirmingReset, titleVisibility: .visible) {
            Button(text("Borrar recuerdos", "Delete memories"), role: .destructive, action: onReset)
            Button(text("Cancelar", "Cancel"), role: .cancel) {}
        } message: {
            Text(text("Esta acción no se puede deshacer. Tus chats y registros financieros se conservan.",
                      "This cannot be undone. Your chats and financial records will stay."))
        }
        .accessibilityIdentifier("identity.memory.screen")
    }
}

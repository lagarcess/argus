import SwiftUI

struct CuadraoHouseholdIntroduction: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let finished: () -> Void
    private var exists: Bool { data.spaces.contains { $0.kind == .household } }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                RegistrationHeading(title: spanish ? "Lo de ustedes,\nen un solo lugar." : "What you share,\nin one place.",
                    detail: spanish ? "Un espacio para las cuentas que llevan juntos. Cada persona conserva sus cuentas privadas."
                        : "A space for the accounts you manage together. Everyone keeps their personal accounts private.")
                Label(spanish ? "Invita cuando quieras" : "Invite when you're ready", systemImage: "person.badge.plus")
                Label(spanish ? "Elijan qué compartir" : "Choose what to share", systemImage: "checkmark.shield")
                RegistrationButton(title: exists ? (spanish ? "Abrir Hogar" : "Open Household")
                    : (spanish ? "Crear Hogar" : "Create Household")) {
                    data.openHousehold(); finished()
                }
            }.padding(24)
        }.navigationTitle(spanish ? "Hogar" : "Household").navigationBarTitleDisplayMode(.inline)
    }
}

struct CuadraoHouseholdSheet: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var cancelInvitation = false
    @FocusState private var focused: Bool
    private var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    switch data.household {
                    case .alone: inviteForm
                    case .pending(let name):
                        RegistrationHeading(title: spanish ? "Esperando a \(name)." : "Waiting for \(name).",
                            detail: spanish ? "Cuando acepte, verá solo las cuentas que compartan en Hogar."
                                : "Once they accept, they'll see only the accounts shared in Household.")
                        Label(spanish ? "Invitación pendiente" : "Invitation pending", systemImage: "envelope")
                            .foregroundStyle(.secondary)
                        Button(spanish ? "Cancelar invitación" : "Cancel invitation", role: .destructive) { cancelInvitation = true }
                            .frame(minHeight: 44)
                        Divider()
                        Text(spanish ? "Vista previa" : "Design preview").font(.caption).foregroundStyle(.secondary)
                        Button(spanish ? "Simular aceptación" : "Simulate acceptance") {
                            data.household = .joined(name); dismiss()
                        }.frame(minHeight: 44)
                    case .joined(let name):
                        RegistrationHeading(title: spanish ? "Su hogar." : "Your household.",
                            detail: spanish ? "Las cuentas personales siguen siendo privadas." : "Personal accounts remain private.")
                        Label(spanish ? "Tú" : "You", systemImage: "person.crop.circle")
                        Divider()
                        Label(name, systemImage: "person.crop.circle")
                    }
                }.padding(24)
            }.background(Color.white)
                .navigationTitle(spanish ? "Hogar" : "Household").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { dismiss() } } }
                .confirmationDialog(spanish ? "¿Cancelar esta invitación?" : "Cancel this invitation?",
                    isPresented: $cancelInvitation, titleVisibility: .visible) {
                    Button(spanish ? "Cancelar invitación" : "Cancel invitation", role: .destructive) {
                        data.household = .alone; dismiss()
                    }
                    Button(spanish ? "Volver" : "Go back", role: .cancel) {}
                }
        }.tint(WelcomePalette.pine).presentationDetents([.large]).presentationDragIndicator(.visible)
    }
    private var inviteForm: some View {
        VStack(alignment: .leading, spacing: 24) {
            RegistrationHeading(title: spanish ? "¿Con quién compartes?" : "Who do you share with?",
                detail: spanish ? "Invitar a alguien no comparte tus cuentas personales." : "Inviting someone doesn't share your personal accounts.")
            VStack(alignment: .leading, spacing: 10) {
                Text(spanish ? "Nombre" : "Name").font(.subheadline)
                TextField(spanish ? "Ej. Alex" : "e.g. Alex", text: $name)
                    .textContentType(.givenName).focused($focused).submitLabel(.done)
                    .onSubmit { focused = false }.modifier(RegistrationField(focused: focused))
                    .onChange(of: name) { _, value in if value.count > 40 { name = String(value.prefix(40)) } }
                    .accessibilityIdentifier("household-invite-name")
            }
            RegistrationButton(title: spanish ? "Preparar invitación" : "Prepare invitation", enabled: !trimmedName.isEmpty) {
                data.household = .pending(trimmedName); dismiss()
            }
            Text(spanish ? "Vista previa: esta invitación no se envía." : "Design preview: this invitation is not sent.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }
}

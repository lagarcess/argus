import SwiftUI

struct CuadraoArchiveAccountReview: View {
    let spanish: Bool
    let archive: () -> Void
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(spanish ? "¿Archivar esta cuenta?" : "Archive this account?").font(CuadraoTypography.feature)
            Text(spanish ? "El historial se conserva. Puedes recuperarla en Cuentas archivadas." : "Its history stays intact. Restore it from Archived accounts.")
            Button(spanish ? "Archivar" : "Archive") { archive(); dismiss() }
                .buttonStyle(.borderedProminent).tint(WelcomePalette.pine)
                .accessibilityIdentifier("accounts.archive.confirm")
            Button(spanish ? "Cancelar" : "Cancel") { dismiss() }
                .accessibilityIdentifier("accounts.archive.cancel")
        }.padding(28).presentationDetents([.medium, .large])
    }
}

struct CuadraoArchivedAccountToast: View {
    let spanish: Bool
    let undo: () -> Void
    let close: () -> Void
    var body: some View {
        HStack {
            Text(spanish ? "Cuenta archivada" : "Account archived")
            Spacer()
            Button(spanish ? "Deshacer" : "Undo", action: undo).accessibilityIdentifier("accounts.archived.undo")
            Button(action: close) { Image(systemName: "xmark").frame(width: 44, height: 44) }
                .accessibilityLabel(spanish ? "Cerrar" : "Close")
                .accessibilityIdentifier("accounts.archived.close")
        }.font(.subheadline).padding(.leading, 20).padding(.trailing, 6)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
            .padding(.horizontal, 20).padding(.bottom, 90)
    }
}

struct CuadraoArchivedAccounts: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text(spanish ? "Sus balances e historial se conservan." : "Balances and history are kept.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    if data.archived.isEmpty {
                        ContentUnavailableView(spanish ? "No hay cuentas archivadas" : "No archived accounts", systemImage: "archivebox")
                    }
                    ForEach(data.archived) { account in
                        VStack(alignment: .leading, spacing: 0) {
                            CanvasAccountRow(account: account, spanish: spanish)
                            CanvasActionRow(title: spanish ? "Restaurar" : "Restore", symbol: "arrow.uturn.backward") {
                                data.archive(account.id, false)
                            }.foregroundStyle(WelcomePalette.pine)
                            Divider()
                        }
                    }
                }.padding(24)
            }.background(WelcomePalette.background)
                .navigationTitle(spanish ? "Cuentas archivadas" : "Archived accounts")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { dismiss() } } }
        }.tint(WelcomePalette.pine)
    }
}

struct CuadraoRenameAccount: View {
    let data: CuadraoAccountsPreview
    let account: CanvasAccount
    let spanish: Bool
    @State private var name = ""
    @FocusState private var focused: Bool
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text(spanish ? "Nombre" : "Name").font(.subheadline)
                TextField(account.kind.title(spanish), text: $name)
                    .autocorrectionDisabled().focused($focused).modifier(RegistrationField(focused: focused))
                    .onChange(of: name) { _, value in if value.count > 60 { name = String(value.prefix(60)) } }
                RegistrationButton(title: spanish ? "Guardar" : "Save", enabled: !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) {
                    var updated = account
                    updated.name = name.trimmingCharacters(in: .whitespacesAndNewlines)
                    data.replace(updated); dismiss()
                }
                Spacer(minLength: 0)
            }.padding(24).background(WelcomePalette.background)
                .navigationTitle(spanish ? "Cambiar nombre" : "Rename account").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button(spanish ? "Cancelar" : "Cancel") { dismiss() } } }
        }.tint(WelcomePalette.pine).presentationDetents([.medium, .large])
            .onAppear { name = account.displayName(spanish) }
    }
}

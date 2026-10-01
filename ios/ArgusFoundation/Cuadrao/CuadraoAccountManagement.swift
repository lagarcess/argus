import SwiftUI

struct CuadraoAccountActions: View {
    @Environment(\.dynamicTypeSize) private var typeSize
    let account: CanvasAccount
    let spanish: Bool
    let rename: () -> Void
    let record: () -> Void
    let archive: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                CanvasAccountIcon(kind: account.kind)
                Text(account.displayName(spanish)).font(.title3.weight(.medium))
            }.padding(.bottom, 12)
            CanvasActionRow(title: spanish ? "Cambiar nombre" : "Rename account", symbol: "pencil", action: rename)
            Divider()
            CanvasActionRow(title: spanish ? "Añadir movimiento" : "Add transaction", symbol: "plus", action: record)
            Divider()
            CanvasActionRow(title: spanish ? "Archivar" : "Archive", symbol: "archivebox", action: archive)
        }.padding(28).presentationDetents(typeSize.isAccessibilitySize ? [.large] : [.height(320)]).presentationDragIndicator(.visible)
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
            }.background(Color.white)
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
            }.padding(24).background(Color.white)
                .navigationTitle(spanish ? "Cambiar nombre" : "Rename account").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button(spanish ? "Cancelar" : "Cancel") { dismiss() } } }
        }.tint(WelcomePalette.pine).presentationDetents([.medium, .large])
            .onAppear { name = account.displayName(spanish) }
    }
}

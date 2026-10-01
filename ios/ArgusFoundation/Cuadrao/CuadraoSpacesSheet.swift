import SwiftUI

struct CuadraoSpacesSheet: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 8) {
                NavigationLink {
                    CuadraoHouseholdIntroduction(data: data, spanish: spanish, finished: { dismiss() })
                } label: {
                    spaceChoice(.household, subtitle: spanish ? "Lo que comparten en casa" : "What you share at home")
                }.buttonStyle(.plain)
                Divider()
                ForEach([CanvasSpaceKind.business, .custom]) { kind in
                    NavigationLink {
                        CuadraoSpaceNameForm(data: data, kind: kind, spanish: spanish, finished: { dismiss() })
                    } label: {
                        spaceChoice(kind, subtitle: kind == .business
                            ? (spanish ? "Tus finanzas del negocio" : "Your business finances")
                            : (spanish ? "Un espacio a tu manera" : "A space of your own"))
                    }.buttonStyle(.plain)
                    Divider()
                }
                NavigationLink {
                    CuadraoManageSpaces(data: data, spanish: spanish, open: { dismiss() })
                } label: {
                    Label(spanish ? "Gestionar espacios" : "Manage spaces", systemImage: "slider.horizontal.3")
                        .font(.subheadline).foregroundStyle(.secondary).frame(minHeight: 52)
                }.buttonStyle(.plain)
                Spacer(minLength: 0)
            }.padding(.horizontal, 24).padding(.top, 12)
                .navigationTitle(spanish ? "Espacios" : "Spaces").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { dismiss() } } }
        }.tint(WelcomePalette.pine).presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
    private func spaceChoice(_ kind: CanvasSpaceKind, subtitle: String) -> some View {
        HStack(spacing: 16) {
            Image(systemName: kind.symbol).font(.title3).frame(width: 28).foregroundStyle(WelcomePalette.pine)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(kind.title(spanish)).font(.body.weight(.medium))
                Text(subtitle).font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary).accessibilityHidden(true)
        }.padding(.vertical, 14).contentShape(Rectangle())
    }
}

private struct CuadraoSpaceNameForm: View {
    let data: CuadraoAccountsPreview
    let kind: CanvasSpaceKind
    let spanish: Bool
    var existing: CanvasSpace?
    let finished: () -> Void
    @State private var name = ""
    @FocusState private var focused: Bool
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Text(spanish ? "Nombre" : "Name").font(.subheadline)
                TextField(kind == .business ? (spanish ? "Ej. Mi estudio" : "e.g. My studio")
                          : (spanish ? "Ej. Mi proyecto" : "e.g. My project"), text: $name)
                    .autocorrectionDisabled().focused($focused).submitLabel(.done)
                    .onSubmit { focused = false }.modifier(RegistrationField(focused: focused))
                    .onChange(of: name) { _, value in if value.count > 40 { name = String(value.prefix(40)) } }
                    .accessibilityIdentifier("space-name")
                if !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !valid {
                    Text(spanish ? "Ya existe un espacio con ese nombre." : "A space already uses that name.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Text(spanish ? "Solo tú tienes acceso a este espacio." : "Only you can access this space.")
                    .font(.subheadline).foregroundStyle(.secondary)
                RegistrationButton(title: existing == nil ? (spanish ? "Crear espacio" : "Create space")
                    : (spanish ? "Guardar" : "Save"), enabled: valid) {
                    data.saveSpace(kind: kind, name: name, existing: existing); finished()
                }
            }.padding(24)
        }.background(Color.white)
            .navigationTitle(existing == nil ? kind.title(spanish) : (spanish ? "Cambiar nombre" : "Rename"))
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { name = existing?.name ?? "" }
    }
    private var valid: Bool { data.spaceNameAvailable(name, except: existing?.id) }
}

private struct CuadraoManageSpaces: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let open: () -> Void
    @State private var deletion: CanvasSpace?
    @State private var deletedID: String?
    var body: some View {
        List {
            Section {
                ForEach(data.visibleSpaces) { space in row(space) }
            }
            if data.spaces.contains(where: { $0.archived && !$0.deleted }) {
                Section(spanish ? "Archivados" : "Archived") {
                    ForEach(data.spaces.filter { $0.archived && !$0.deleted }) { space in row(space) }
                }
            }
            if data.spaces.contains(where: \.deleted) {
                Section(spanish ? "Eliminados recientemente" : "Recently deleted") {
                    ForEach(data.spaces.filter(\.deleted)) { space in row(space) }
                }
            }
            if let deletedID {
                Button(spanish ? "Deshacer eliminación" : "Undo deletion") {
                    data.restoreSpace(deletedID); self.deletedID = nil
                }
            }
        }.navigationTitle(spanish ? "Gestionar espacios" : "Manage spaces").navigationBarTitleDisplayMode(.inline)
            .confirmationDialog(spanish ? "¿Eliminar este espacio vacío?" : "Delete this empty space?",
                isPresented: Binding(get: { deletion != nil }, set: { if !$0 { deletion = nil } }), titleVisibility: .visible) {
                if let deletion {
                    Button(spanish ? "Eliminar espacio" : "Delete space", role: .destructive) {
                        data.deleteSpace(deletion); deletedID = deletion.id; self.deletion = nil
                    }
                }
                Button(spanish ? "Cancelar" : "Cancel", role: .cancel) { deletion = nil }
            } message: {
                Text(spanish ? "Puedes restaurarlo desde Eliminados recientemente." : "You can restore it from Recently deleted.")
            }
    }
    private func row(_ space: CanvasSpace) -> some View {
        HStack(spacing: 14) {
            Image(systemName: space.kind.symbol).frame(width: 24).foregroundStyle(WelcomePalette.pine).accessibilityHidden(true)
            Button {
                if space.deleted || space.archived { data.restoreSpace(space.id) }
                data.selectedSpaceID = space.id; open()
            } label: {
                VStack(alignment: .leading, spacing: 4) {
                    Text(space.title(spanish)).foregroundStyle(.primary)
                    Text(space.deleted || space.archived ? (spanish ? "Restaurar y abrir" : "Restore and open")
                         : space.kind.title(spanish)).font(.caption).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            }.buttonStyle(.plain)
            if space.isPrivate && !space.deleted {
                Menu {
                    NavigationLink(spanish ? "Cambiar nombre" : "Rename") {
                        CuadraoSpaceNameForm(data: data, kind: space.kind, spanish: spanish,
                            existing: space, finished: open)
                    }
                    Button(space.archived ? (spanish ? "Restaurar" : "Restore") : (spanish ? "Archivar" : "Archive"),
                        systemImage: space.archived ? "arrow.uturn.backward" : "archivebox") {
                        data.archiveSpace(space.id, archived: !space.archived)
                    }
                    if data.canDeleteSpace(space) {
                        Button(spanish ? "Eliminar espacio vacío" : "Delete empty space", systemImage: "trash", role: .destructive) { deletion = space }
                    }
                } label: {
                    Image(systemName: "ellipsis").frame(width: 44, height: 44)
                }.accessibilityLabel((spanish ? "Opciones de " : "Options for ") + space.title(spanish))
            }
        }
    }
}

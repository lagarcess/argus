import SwiftUI

/// Local design rows share their conversation objects with Chat and Search.
struct CuadraoChatHistory: View {
    let store: CuadraoChatPreview
    let spanish: Bool
    let open: (CanvasChatThread) -> Void
    let newChat: () -> Void
    @State private var query = ""
    @State private var scope = Scope.recent
    @State private var renaming: CanvasChatThread?
    @State private var renameDraft = ""
    @State private var showRename = false
    @State private var showDelete = false
    @State private var deleting: CanvasChatThread?
    private var es: Bool { spanish }
    private enum Scope: Int, CaseIterable { case recent, archived, deleted }

    private var rows: [CanvasChatThread] {
        let search = query.trimmingCharacters(in: .whitespacesAndNewlines)
        return store.visibleThreads.filter {
            (scope == .deleted ? $0.deleted : !$0.deleted && $0.archived == (scope == .archived))
                && (search.isEmpty || $0.title.localizedStandardContains(search))
        }.sorted { ($0.lastMessageDate ?? .distantPast) > ($1.lastMessageDate ?? .distantPast) }
    }
    var body: some View {
        VStack(spacing: 12) {
            Picker(es ? "Ver chats" : "Show chats", selection: $scope) {
                Text(es ? "Recientes" : "Recent").tag(Scope.recent)
                Text(es ? "Archivados" : "Archived").tag(Scope.archived)
                Text(es ? "Eliminados" : "Deleted").tag(Scope.deleted)
            }.pickerStyle(.segmented).padding(.horizontal, 24)
            List {
                if rows.isEmpty { empty }
                else if scope == .recent {
                    group(rows.filter(\.pinned), title: es ? "Fijados" : "Pinned")
                    group(rows.filter { !$0.pinned }, title: es ? "Recientes" : "Recent")
                } else { ForEach(rows) { row($0) } }
            }.listStyle(.plain).scrollContentBackground(.hidden)
                .searchable(text: $query, prompt: es ? "Buscar chats" : "Search chats")
            Button(action: newChat) {
                Label { Text(es ? "Nuevo chat" : "New chat") } icon: {
                    Image("CuadraoNewChat").resizable().scaledToFit().frame(width: 20, height: 20)
                }.frame(minHeight: 44)
            }.accessibilityIdentifier("history-new")
            Text(es ? "Vista previa · Chats locales" : "Preview · Local chats")
                .font(.caption).foregroundStyle(.secondary).padding(.bottom, 16)
        }
        .alert(es ? "Cambiar nombre" : "Rename", isPresented: $showRename) {
            TextField(es ? "Nombre del chat" : "Chat name", text: $renameDraft)
            Button(es ? "Cancelar" : "Cancel", role: .cancel) { renaming = nil }
            Button(es ? "Guardar" : "Save") {
                renaming?.title = String(renameDraft.trimmingCharacters(in: .whitespacesAndNewlines).prefix(80))
                renaming = nil
            }.disabled(renameDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .confirmationDialog(es ? "¿Eliminar chat?" : "Delete chat?", isPresented: $showDelete, titleVisibility: .visible) {
            Button(es ? "Eliminar chat" : "Delete chat", role: .destructive) {
                if let deleting { store.delete(deleting) }; deleting = nil
            }
        } message: { Text(es ? "Podrás recuperarlo en Eliminados." : "You can recover it in Deleted.") }
    }

    @ViewBuilder private func group(_ items: [CanvasChatThread], title: String) -> some View {
        if !items.isEmpty {
            Section { ForEach(items) { row($0) } } header: {
                Text(title).font(.caption.weight(.medium)).textCase(nil).foregroundStyle(.secondary)
            }
        }
    }

    private func row(_ thread: CanvasChatThread) -> some View {
        Button { open(thread) } label: {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(thread.title.isEmpty ? (es ? "Nuevo chat" : "New chat") : thread.title)
                    .font(.body.weight(thread.unread ? .semibold : .regular)).lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 6) {
                    if thread.unread { Circle().fill(WelcomePalette.pine).frame(width: 6, height: 6) }
                    else if store.current.id == thread.id && !store.temporary {
                        Image(systemName: "checkmark").font(.caption2).foregroundStyle(WelcomePalette.pine)
                    }
                    if let date = thread.lastMessageDate { CuadraoChatDate(date: date, spanish: es) }
                }.accessibilityHidden(true)
            }.frame(minHeight: 52).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("history-row-" + thread.id)
            .accessibilityLabel(thread.title.isEmpty ? (es ? "Nuevo chat" : "New chat") : thread.title)
            .accessibilityValue(accessibilityValue(thread))
            .accessibilityActions { actions(thread) }
            .padding(.vertical, 4)
            .listRowInsets(EdgeInsets(top: 0, leading: 24, bottom: 0, trailing: 24))
            .listRowBackground(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
            .contextMenu { actions(thread) }
            .swipeActions(edge: .leading, allowsFullSwipe: true) {
                if scope == .recent {
                    Button { thread.pinned.toggle() } label: {
                        Label(thread.pinned ? (es ? "Desfijar" : "Unpin") : (es ? "Fijar" : "Pin"), systemImage: thread.pinned ? "pin.slash" : "pin")
                    }.tint(Color(red: 0.62, green: 0.36, blue: 0.08))
                }
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                if scope == .recent {
                    Button { store.archive(thread) } label: { Label(es ? "Archivar" : "Archive", systemImage: "archivebox") }
                        .tint(Color(red: 0.34, green: 0.41, blue: 0.47))
                } else {
                    Button { store.restore(thread) } label: { Label(es ? "Restaurar" : "Restore", systemImage: "arrow.uturn.backward") }
                        .tint(WelcomePalette.pine)
                }
            }
    }

    private func accessibilityValue(_ thread: CanvasChatThread) -> String {
        let state = thread.deleted ? (es ? "Restaurar y abrir" : "Restore and open")
            : thread.unread ? (es ? "No leído" : "Unread")
            : store.current.id == thread.id && !store.temporary ? (es ? "Actual" : "Current") : nil
        return [state, thread.lastMessageDate.map { CanvasChatRecency.label($0, spanish: es) }]
            .compactMap { $0 }.joined(separator: ", ")
    }

    @ViewBuilder private func actions(_ thread: CanvasChatThread) -> some View {
        if thread.deleted {
            Button(es ? "Restaurar" : "Restore", systemImage: "arrow.uturn.backward") { store.restore(thread) }
        } else {
            Button(thread.unread ? (es ? "Marcar como leído" : "Mark as read") : (es ? "Marcar como no leído" : "Mark as unread"), systemImage: thread.unread ? "envelope.open" : "envelope") { thread.unread.toggle() }
            Button(thread.pinned ? (es ? "Desfijar" : "Unpin") : (es ? "Fijar" : "Pin"), systemImage: thread.pinned ? "pin.slash" : "pin") { thread.pinned.toggle() }
            Button(es ? "Cambiar nombre" : "Rename", systemImage: "pencil") { renameDraft = thread.title; renaming = thread; showRename = true }
            if thread.archived {
                Button(es ? "Restaurar" : "Restore", systemImage: "arrow.uturn.backward") { store.restore(thread) }
            } else {
                Button(es ? "Archivar" : "Archive", systemImage: "archivebox") { store.archive(thread) }
            }
            Divider()
            Button(es ? "Eliminar" : "Delete", systemImage: "trash", role: .destructive) { deleting = thread; showDelete = true }
        }
    }

    private var empty: some View {
        let searching = !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return ContentUnavailableView(searching ? (es ? "Sin resultados" : "No results") : (es ? "Sin chats" : "No chats"),
            systemImage: searching ? "magnifyingglass" : "bubble.left.and.bubble.right",
            description: Text(searching ? (es ? "Prueba otra búsqueda." : "Try another search.")
                : (es ? "Los chats aparecerán aquí." : "Chats will appear here.")))
    }
}

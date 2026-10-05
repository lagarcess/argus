import SwiftUI

/// One collection interaction vocabulary. State and persistence stay with the item owner.
struct CuadraoOrderedCollection<Item: Identifiable, Row: View>: View where Item.ID == UUID {
    let items: [Item]
    let spanish: Bool
    var spacing: CGFloat = 18
    let identifier: (Item) -> String
    let open: (Item) -> Void
    let edit: (Item) -> Void
    var canEdit: (Item) -> Bool = { _ in true }
    let archive: (Item) -> Void
    let reorder: ([UUID]) -> Void
    @ViewBuilder let row: (Item) -> Row

    var body: some View {
        if #available(iOS 27.0, *), !ProcessInfo.processInfo.arguments.contains("--legacy-collection") {
            VStack(spacing: spacing) {
                ForEach(items) { item in
                    itemButton(item)
                        .swipeActions(edge: .leading, allowsFullSwipe: false) {
                            if canEdit(item) { Button { edit(item) } label: { Image(systemName: "pencil") }.tint(.blue).accessibilityLabel(spanish ? "Editar" : "Edit") }
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button { archive(item) } label: { Image(systemName: "archivebox") }.tint(.orange).accessibilityLabel(spanish ? "Archivar" : "Archive")
                        }
                }.reorderable()
            }
            .reorderContainer(for: Item.self) { difference in
                switch difference.destination.position {
                case .before(let id): move(difference.sources, before: id)
                case .end: move(difference.sources, before: nil)
                @unknown default: break
                }
            }.swipeActionsContainer()
        } else {
            // Older systems keep explicit controls and native drag/drop; no competing hold menu.
            VStack(spacing: spacing) {
                ForEach(items) { item in
                    VStack(alignment: .leading, spacing: 0) {
                        itemButton(item)
                            .draggable(item.id.uuidString)
                            .dropDestination(for: String.self) { values, _ in
                                guard let value = values.first, let id = UUID(uuidString: value), items.contains(where: { $0.id == id }) else { return false }
                                move([id], before: item.id); return true
                            }
                        HStack {
                            if canEdit(item) { Button { edit(item) } label: { Label(spanish ? "Editar" : "Edit", systemImage: "pencil").frame(minHeight: 44).contentShape(Rectangle()) }.buttonStyle(.plain) }
                            Spacer()
                            Button { archive(item) } label: { Label(spanish ? "Archivar" : "Archive", systemImage: "archivebox").frame(minHeight: 44).contentShape(Rectangle()) }.buttonStyle(.plain)
                        }.font(.caption).frame(minHeight: 44)
                    }
                }
            }
        }
    }
    private func itemButton(_ item: Item) -> some View {
        Button { open(item) } label: { row(item).contentShape(Rectangle()) }
            .buttonStyle(.plain).accessibilityIdentifier(identifier(item))
            .accessibilityAction(named: Text(spanish ? "Archivar" : "Archive")) { archive(item) }
            .accessibilityActions {
                if canEdit(item) { Button(spanish ? "Editar" : "Edit") { edit(item) } }
                if items.first?.id != item.id {
                    Button(spanish ? "Mover arriba" : "Move up") { step(item.id, by: -1) }
                }
                if items.last?.id != item.id {
                    Button(spanish ? "Mover abajo" : "Move down") { step(item.id, by: 1) }
                }
            }
    }
    private func step(_ id: UUID, by delta: Int) {
        var ids = items.map(\.id)
        guard let index = ids.firstIndex(of: id), ids.indices.contains(index + delta) else { return }
        ids.swapAt(index, index + delta); reorder(ids)
    }
    private func move(_ moving: [UUID], before destination: UUID?) {
        let current = items.map(\.id)
        guard !moving.isEmpty, Set(moving).isSubset(of: Set(current)), destination.map({ !moving.contains($0) }) ?? true else { return }
        var result = current.filter { !moving.contains($0) }
        let index = destination.flatMap { result.firstIndex(of: $0) } ?? result.endIndex
        result.insert(contentsOf: current.filter { moving.contains($0) }, at: index)
        reorder(result)
    }
}

import Foundation

/// Apply a visible collection's order without moving archived/out-of-scope records.
enum CuadraoCollectionOrder {
    static func applying<Item: Identifiable>(_ ids: [UUID], to items: [Item]) -> [Item] where Item.ID == UUID {
        guard Set(ids).count == ids.count, Set(ids).isSubset(of: Set(items.map(\.id))) else { return items }
        let byID = Dictionary(uniqueKeysWithValues: items.map { ($0.id, $0) })
        var ordered = ids.compactMap { byID[$0] }.makeIterator()
        let selected = Set(ids)
        return items.map { selected.contains($0.id) ? ordered.next()! : $0 }
    }
}

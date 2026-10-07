import Foundation

/// The order a person drags their Home accounts into. It lives on this device, per signed-in person;
/// the server keeps no account order, and an account it has not seen here goes last.
enum ConnectedAccountOrder {
    static func key(for userID: String) -> String { "cuadrao.account-order." + userID }

    static func load(for userID: String, defaults: UserDefaults = .standard) -> [UUID] {
        (defaults.stringArray(forKey: key(for: userID)) ?? []).compactMap(UUID.init(uuidString:))
    }

    static func save(_ ids: [UUID], for userID: String, defaults: UserDefaults = .standard) {
        defaults.set(ids.map(\.uuidString), forKey: key(for: userID))
    }

    static func applying<Item: Identifiable>(_ order: [UUID], to items: [Item]) -> [Item] where Item.ID == UUID {
        let rank = Dictionary(order.enumerated().map { ($0.element, $0.offset) }, uniquingKeysWith: { first, _ in first })
        return items.enumerated().sorted { left, right in
            switch (rank[left.element.id], rank[right.element.id]) {
            case let (a?, b?): a < b
            case (.some, nil): true
            case (nil, .some): false
            case (nil, nil): left.offset < right.offset
            }
        }.map(\.element)
    }

    /// `moving` goes before `destination`, or to the end when `destination` is nil.
    static func moving(_ moving: UUID, before destination: UUID?, in ids: [UUID]) -> [UUID] {
        guard ids.contains(moving), destination != moving, destination.map(ids.contains) ?? true else { return ids }
        var result = ids.filter { $0 != moving }
        let index = destination.flatMap { result.firstIndex(of: $0) } ?? result.endIndex
        result.insert(moving, at: index)
        return result
    }
}

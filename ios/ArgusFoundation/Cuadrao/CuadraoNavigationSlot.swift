import Foundation

enum CuadraoTab: Int, CaseIterable, Identifiable {
    case home, plan, assistant, search, profile
    var id: Self { self }
}

/// One slot of the navigation bar: a destination, or the add-movement action that takes the
/// assistant's place when the build has no assistant. The action is never a tab.
enum CuadraoNavigationSlot: Hashable, Identifiable {
    case tab(CuadraoTab)
    case add
    var id: Self { self }

    static func slots(hasAssistant: Bool) -> [CuadraoNavigationSlot] {
        CuadraoTab.allCases.map { tab in
            guard tab == .assistant else { return .tab(tab) }
            return hasAssistant ? .tab(tab) : .add
        }
    }
}

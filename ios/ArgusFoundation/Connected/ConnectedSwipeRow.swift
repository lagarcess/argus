import SwiftUI

struct ConnectedSwipeAction: Identifiable {
    let id: String
    let title: String
    let symbol: String
    let tint: Color
    let action: () -> Void
}

/// Swipe actions for connected Home rows outside a List on iOS 27. Nothing runs
/// on a full swipe, every action is also an accessibility action, and older
/// systems keep the row's own menu and detail actions.
struct ConnectedSwipeRow<Content: View>: View {
    let leading: [ConnectedSwipeAction]
    let trailing: [ConnectedSwipeAction]
    @ViewBuilder let content: () -> Content

    static var swipesAvailable: Bool {
        if #available(iOS 27.0, *) { return !ProcessInfo.processInfo.arguments.contains("--legacy-collection") }
        return false
    }

    var body: some View {
        if #available(iOS 27.0, *), Self.swipesAvailable {
            accessible
                .swipeActions(edge: .leading, allowsFullSwipe: false) { buttons(leading) }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) { buttons(trailing) }
        } else { accessible }
    }

    private var accessible: some View {
        content().accessibilityActions {
            ForEach(leading + trailing) { action in Button(action.title, action: action.action) }
        }
    }

    private func buttons(_ actions: [ConnectedSwipeAction]) -> some View {
        ForEach(actions) { action in
            Button(action: action.action) { Image(systemName: action.symbol) }
                .tint(action.tint).accessibilityLabel(action.title).accessibilityIdentifier(action.id)
        }
    }
}

extension View {
    /// Hosts swipe-capable rows inside a plain stack on iOS 27; unchanged before.
    @ViewBuilder func connectedSwipeContainer() -> some View {
        if #available(iOS 27.0, *), ConnectedSwipeRow<EmptyView>.swipesAvailable { swipeActionsContainer() } else { self }
    }
}

import SwiftUI

struct ConnectedSwipeAction: Identifiable {
    let id: String
    let title: String
    let symbol: String
    let tint: Color
    let action: () -> Void
}

/// The action set a row registers with the iOS 27 swipe container. Outside a List
/// the container reads swipe content once per registration, so a different set
/// must be a new registration, and an edge without actions registers no swipe.
struct ConnectedSwipeRegistration: Hashable {
    let leading: [String]
    let trailing: [String]

    func swipes(_ edge: HorizontalEdge) -> Bool {
        !(edge == .leading ? leading : trailing).isEmpty
    }
}

/// Swipe actions for connected Home rows outside a List on iOS 27. Nothing runs
/// on a full swipe, every action is also an accessibility action, and older
/// systems keep the row's own menu and detail actions. The rows' scroll view
/// carries `connectedSwipeContainer()` so scrolling and other rows close them.
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
            let registration = ConnectedSwipeRegistration(leading: leading.map(\.id), trailing: trailing.map(\.id))
            accessible
                .modifier(ConnectedSwipeEdge(edge: .leading, actions: leading, registered: registration.swipes(.leading)))
                .modifier(ConnectedSwipeEdge(edge: .trailing, actions: trailing, registered: registration.swipes(.trailing)))
                .id(registration)
        } else { accessible }
    }

    private var accessible: some View {
        content().accessibilityActions {
            ForEach(leading + trailing) { action in Button(action.title, action: action.action) }
        }
    }
}

@available(iOS 27.0, *)
private struct ConnectedSwipeEdge: ViewModifier {
    let edge: HorizontalEdge
    let actions: [ConnectedSwipeAction]
    let registered: Bool

    func body(content: Content) -> some View {
        if registered {
            content.swipeActions(edge: edge, allowsFullSwipe: false) {
                ForEach(actions) { action in
                    Button(action: action.action) { Image(systemName: action.symbol) }
                        .tint(action.tint).accessibilityLabel(action.title).accessibilityIdentifier(action.id)
                }
            }
        } else { content }
    }
}

extension View {
    /// Coordinates connected swipe rows on iOS 27; apply it to the scroll view that holds them.
    @ViewBuilder func connectedSwipeContainer() -> some View {
        if #available(iOS 27.0, *), ConnectedSwipeRow<EmptyView>.swipesAvailable { swipeActionsContainer() } else { self }
    }
}

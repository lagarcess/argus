import SwiftUI

// One treatment for scrolling content beneath Cuadrao's stationary controls.
extension View {
    @ViewBuilder
    func cuadraoScrollBar<Bar: View>(edge: VerticalEdge, @ViewBuilder content: () -> Bar) -> some View {
        if #available(iOS 26.0, *) {
            safeAreaBar(edge: edge, spacing: 0, content: content)
        } else {
            safeAreaInset(edge: edge, spacing: 0) {
                content().background(.regularMaterial)
            }
        }
    }

    @ViewBuilder
    func cuadraoSoftScrollEdges() -> some View {
        if #available(iOS 26.0, *) {
            scrollEdgeEffectStyle(.soft, for: .vertical)
        } else {
            self
        }
    }
}

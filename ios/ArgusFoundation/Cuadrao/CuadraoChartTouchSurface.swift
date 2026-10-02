import SwiftUI
import UIKit

/// Inspection claims a held touch; ordinary pans belong to the surrounding native scroll views.
struct CuadraoChartTouchSurface: UIViewRepresentable {
    let inspect: (CGPoint) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear
        view.isAccessibilityElement = false
        view.accessibilityElementsHidden = true
        let hold = UILongPressGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.hold(_:)))
        hold.minimumPressDuration = 0.2
        hold.allowableMovement = 10
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tap(_:)))
        tap.require(toFail: hold)
        view.addGestureRecognizer(hold)
        view.addGestureRecognizer(tap)
        return view
    }
    func updateUIView(_ view: UIView, context: Context) { context.coordinator.owner = self }
    final class Coordinator: NSObject {
        var owner: CuadraoChartTouchSurface
        init(_ owner: CuadraoChartTouchSurface) { self.owner = owner }
        @objc func hold(_ recognizer: UILongPressGestureRecognizer) {
            if recognizer.state == .began || recognizer.state == .changed { owner.inspect(recognizer.location(in: recognizer.view)) }
        }
        @objc func tap(_ recognizer: UITapGestureRecognizer) {
            if recognizer.state == .ended { owner.inspect(recognizer.location(in: recognizer.view)) }
        }
    }
}

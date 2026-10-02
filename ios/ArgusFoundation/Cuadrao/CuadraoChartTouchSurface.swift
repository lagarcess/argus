import SwiftUI
import UIKit

/// Reject vertical pans before recognition so the containing ScrollView keeps them.
struct CuadraoChartTouchSurface: UIViewRepresentable {
    let inspect: (CGPoint) -> Void
    let page: (Int) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear
        view.isAccessibilityElement = false
        view.accessibilityElementsHidden = true
        let hold = UILongPressGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.hold(_:)))
        hold.minimumPressDuration = 0.2
        hold.allowableMovement = 10
        let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.pan(_:)))
        pan.maximumNumberOfTouches = 1
        pan.delegate = context.coordinator
        pan.require(toFail: hold)
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tap(_:)))
        tap.require(toFail: hold)
        view.addGestureRecognizer(hold)
        view.addGestureRecognizer(pan)
        view.addGestureRecognizer(tap)
        return view
    }
    func updateUIView(_ view: UIView, context: Context) { context.coordinator.owner = self }
    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var owner: CuadraoChartTouchSurface
        init(_ owner: CuadraoChartTouchSurface) { self.owner = owner }
        func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
            guard let pan = gestureRecognizer as? UIPanGestureRecognizer else { return true }
            let velocity = pan.velocity(in: pan.view)
            return abs(velocity.x) > abs(velocity.y) * 1.4
        }
        @objc func hold(_ recognizer: UILongPressGestureRecognizer) {
            if recognizer.state == .began || recognizer.state == .changed { owner.inspect(recognizer.location(in: recognizer.view)) }
        }
        @objc func tap(_ recognizer: UITapGestureRecognizer) {
            if recognizer.state == .ended { owner.inspect(recognizer.location(in: recognizer.view)) }
        }
        @objc func pan(_ recognizer: UIPanGestureRecognizer) {
            guard recognizer.state == .ended else { return }
            let delta = recognizer.translation(in: recognizer.view)
            guard abs(delta.x) > 25, abs(delta.x) > abs(delta.y) * 1.4 else { return }
            owner.page(delta.x > 0 ? -1 : 1)
        }
    }
}

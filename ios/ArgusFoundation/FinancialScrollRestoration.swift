import Foundation

struct FinancialScrollRestoration: Equatable {
    let id = UUID()
    let anchor: String
    let offset: Double
    var permitsBoundaryFallback = false

    enum Adjustment: Equatable { case complete, move(Double), waitForLayout }

    func adjustment(rowOffset: Double, contentOffset: Double, minimum: Double, maximum: Double) -> Adjustment {
        let delta = rowOffset - offset
        if abs(delta) < 0.5 { return .complete }
        let target = min(maximum, max(minimum, contentOffset + delta))
        if abs(target - contentOffset) < 0.5 {
            return permitsBoundaryFallback ? .complete : .waitForLayout
        }
        return .move(target)
    }
}

enum FinancialScrollRestorationPhase: Equatable {
    case waitingForContent, restoring(FinancialScrollRestoration), tracking

    mutating func prepare(anchor: String?, offset: Double?, availableAnchors: [String]?) {
        guard let availableAnchors else { return }
        switch self {
        case .waitingForContent:
            if let anchor, availableAnchors.contains(anchor) {
                self = .restoring(FinancialScrollRestoration(anchor: anchor, offset: offset ?? 0))
            } else { self = .tracking }
        case .restoring(let restoration):
            if !availableAnchors.contains(restoration.anchor) { self = .tracking }
        case .tracking: break
        }
    }

    mutating func restored(_ id: UUID) {
        guard case .restoring(let restoration) = self, restoration.id == id else { return }
        self = .tracking
    }

    mutating func userScrolled() { self = .tracking }
}

@MainActor
struct FinancialScrollContext {
    let id: String
    let anchor: String?
    let offset: Double?
    let availableAnchors: [String]?
    let active: Bool
    let remember: @MainActor (String, Double) -> Void
}

#if canImport(UIKit)
import SwiftUI
import UIKit

struct FinancialRestoringScrollView<Content: View>: View {
    let context: FinancialScrollContext
    @ViewBuilder let content: () -> Content
    @StateObject private var scroll = FinancialScrollOffset()
    @State private var phase = FinancialScrollRestorationPhase.waitingForContent
    @State private var visible = false

    var body: some View {
        ScrollView {
            content().background(FinancialScrollProbe(controller: scroll, onReady: updatePosition))
        }
        .coordinateSpace(name: "financial.scroll.viewport")
        .onPreferenceChange(FinancialScrollRowFrames.self) { frames in
            scroll.frames = frames
            updatePosition()
        }
        .onAppear { visible = true; updatePosition() }
        .onDisappear { visible = false }
        .task(id: context.active ? context.availableAnchors : nil) {
            await Task.yield()
            guard !Task.isCancelled else { return }
            scroll.view?.layoutIfNeeded()
            updatePosition()
        }
        .simultaneousGesture(DragGesture(minimumDistance: 1).onChanged { _ in
            guard visible, context.active, context.availableAnchors != nil else { return }
            phase.userScrolled()
            updatePosition()
        })
    }

    private func updatePosition() {
        guard visible, context.active, let anchors = context.availableAnchors else { return }
        phase.prepare(anchor: context.anchor, offset: context.offset, availableAnchors: anchors)
        switch phase {
        case .waitingForContent: return
        case .restoring(let restoration):
            if let frame = scroll.frames[restoration.anchor], scroll.restore(restoration, currentRowOffset: frame.minY) {
                phase.restored(restoration.id)
            }
        case .tracking:
            guard let row = scroll.frames.filter({ anchors.contains($0.key) && $0.value.maxY > 0 })
                .min(by: { $0.value.minY < $1.value.minY }) else { return }
            context.remember(row.key, row.value.minY)
        }
    }
}

struct FinancialScrollRowFrames: PreferenceKey {
    static let defaultValue: [String: CGRect] = [:]
    static func reduce(value: inout [String: CGRect], nextValue: () -> [String: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { _, new in new })
    }
}

extension View {
    func financialScrollAnchor(_ id: String, in coordinateSpace: String = "financial.scroll.viewport") -> some View {
        background(GeometryReader { geometry in
            Color.clear.preference(key: FinancialScrollRowFrames.self,
                value: [id: geometry.frame(in: .named(coordinateSpace))])
        })
    }
}

@MainActor
final class FinancialScrollOffset: ObservableObject {
    weak var view: UIScrollView?
    var frames: [String: CGRect] = [:]

    func restore(_ restoration: FinancialScrollRestoration, currentRowOffset: Double) -> Bool {
        guard let view else { return false }
        let minimum = -view.adjustedContentInset.top
        let maximum = max(minimum, view.contentSize.height - view.bounds.height + view.adjustedContentInset.bottom)
        switch restoration.adjustment(rowOffset: currentRowOffset, contentOffset: view.contentOffset.y,
                                      minimum: minimum, maximum: maximum) {
        case .complete: return true
        case .waitForLayout: return false
        case .move(let y):
            view.setContentOffset(CGPoint(x: view.contentOffset.x, y: y), animated: false)
            return false
        }
    }
}

struct FinancialScrollProbe: UIViewRepresentable {
    let controller: FinancialScrollOffset
    var onReady: () -> Void = {}

    func makeUIView(context: Context) -> UIView { UIView() }
    func updateUIView(_ view: UIView, context: Context) {
        DispatchQueue.main.async {
            var parent = view.superview
            while let current = parent {
                if let scroll = current as? UIScrollView {
                    guard controller.view !== scroll else { return }
                    controller.view = scroll
                    onReady()
                    return
                }
                parent = current.superview
            }
        }
    }
}
#endif

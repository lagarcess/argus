import SwiftUI

struct CuadraoAllocationSegment: Identifiable {
    let id: String
    let title: String
    let fraction: Double
    let color: Color
}

struct CuadraoAllocationBar: View {
    let segments: [CuadraoAllocationSegment]
    @Binding var selection: String?
    let identifier: String
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body: some View {
        GeometryReader { geometry in
            let width = max(0, geometry.size.width - 8)
            ZStack(alignment: .topLeading) {
                ForEach(segments) { segment in
                    let active = selection == nil || selection == segment.id
                    let segmentWidth = width * segment.fraction
                    let start = width * segments.prefix { $0.id != segment.id }.reduce(0.0) { $0 + $1.fraction }
                    ZStack(alignment: .topLeading) {
                        CuadraoAllocationBlock(color: segment.color, filled: active,
                            exposedSide: segment.id == segments.first?.id || selection == segment.id,
                            start: start, segmentWidth: segmentWidth)
                        Button {
                            withAnimation(reduceMotion ? .easeInOut(duration: 0.15) : .spring(response: 0.42, dampingFraction: 0.85)) {
                                selection = selection == segment.id ? nil : segment.id
                            }
                        } label: {
                            Color.clear.frame(width: segmentWidth, height: 62).contentShape(Rectangle())
                        }.buttonStyle(.plain).offset(x: start + 8, y: 22)
                            .accessibilityLabel(segment.title)
                            .accessibilityValue(segment.fraction.formatted(.percent.precision(.fractionLength(1))))
                            .accessibilityIdentifier(identifier + segment.id)
                    }.offset(y: !reduceMotion && selection == segment.id ? -10 : 0).opacity(active ? 1 : 0.28)
                }
            }
        }.frame(height: 104)
    }
}

private struct CuadraoAllocationBlock: View {
    let color: Color
    let filled: Bool
    let exposedSide: Bool
    let start: CGFloat
    let segmentWidth: CGFloat
    var body: some View {
        Canvas { context, _ in
            let depth: CGFloat = 8
            let topY: CGFloat = 22
            let front = Path(CGRect(x: start + depth, y: topY + depth, width: segmentWidth, height: 54))
            let top = Path { path in
                path.move(to: CGPoint(x: start, y: topY))
                path.addLine(to: CGPoint(x: start + segmentWidth, y: topY))
                path.addLine(to: CGPoint(x: start + segmentWidth + depth, y: topY + depth))
                path.addLine(to: CGPoint(x: start + depth, y: topY + depth)); path.closeSubpath()
            }
            let side = Path { path in
                path.move(to: CGPoint(x: start, y: topY))
                path.addLine(to: CGPoint(x: start + depth, y: topY + depth))
                path.addLine(to: CGPoint(x: start + depth, y: topY + 62))
                path.addLine(to: CGPoint(x: start, y: topY + 54)); path.closeSubpath()
            }
            context.fill(top, with: .color(color.opacity(filled ? 0.55 : 0.04)))
            if exposedSide { context.fill(side, with: .color(color.opacity(filled ? 0.65 : 0.04))) }
            context.fill(front, with: .color(color.opacity(filled ? 0.8 : 0.03)))
            for path in (exposedSide ? [top, side, front] : [top, front]) {
                context.stroke(path, with: .color(filled ? .white.opacity(0.65) : color), lineWidth: 0.75)
            }
        }.accessibilityHidden(true).allowsHitTesting(false)
    }
}

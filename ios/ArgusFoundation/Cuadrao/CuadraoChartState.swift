import SwiftUI

/// Decorative forms never stand in for financial observations.
struct CuadraoChartState: View {
    let title: String
    let detail: String
    var loading = false
    var motionEnabled = true
    var actionTitle: String?
    var action: (() -> Void)?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var breathing = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            ZStack(alignment: .bottomTrailing) {
                HStack(alignment: .bottom, spacing: 16) {
                    ForEach(Array([0.8, 0.62, 0.35, 0.52, 0.7].enumerated()), id: \.offset) { _, height in
                        RoundedRectangle(cornerRadius: 16)
                            .fill(LinearGradient(colors: [WelcomePalette.ink.opacity(0.12), WelcomePalette.ink.opacity(0.015)], startPoint: .top, endPoint: .bottom))
                            .frame(height: 150 * height)
                    }
                }
                if !loading {
                    CuadraoChartLandscape().frame(width: 84, height: 76).offset(x: 4, y: 12)
                }
            }.frame(height: 150).opacity(loading && breathing ? 0.45 : 1)
                .accessibilityHidden(true).allowsHitTesting(false)
            VStack(alignment: .leading, spacing: 6) {
                Text(title).font(CuadraoTypography.section)
                Text(detail).font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            }.fixedSize(horizontal: false, vertical: true)
            if let actionTitle, let action {
                Button(actionTitle, action: action).font(CuadraoTypography.action)
                    .frame(minHeight: 44).accessibilityIdentifier("chart-state-action")
            }
        }.padding(.vertical, 16)
            .task(id: reduceMotion || !motionEnabled) {
                breathing = false
                if loading && motionEnabled && !reduceMotion {
                    withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) { breathing = true }
                }
            }
    }
}

/// Quiet cover art for empty/loading chart shells. Lives next to chart state so
/// design-preview Home does not import the parked Plan visuals module.
private struct CuadraoChartLandscape: View {
    var body: some View {
        GeometryReader { g in
            ZStack {
                Circle().fill(WelcomePalette.pine.opacity(0.10)).frame(width: g.size.width * 0.8)
                Circle().fill(WelcomePalette.pine.opacity(0.24))
                    .frame(width: g.size.width * 0.29, height: g.size.width * 0.29)
                    .offset(x: g.size.width * 0.16, y: -g.size.height * 0.19)
                ForEach(0..<3) { index in
                    CuadraoChartWave(crest: CGFloat(index) * 0.12)
                        .fill(WelcomePalette.pine.opacity(0.12 + Double(index) * 0.09))
                        .frame(height: g.size.height * 0.5)
                        .offset(y: g.size.height * 0.15 + CGFloat(index) * 9)
                }
                Image(systemName: "water.waves").font(.system(size: 27, weight: .light))
                    .foregroundStyle(WelcomePalette.pine).offset(x: -g.size.width * 0.13, y: g.size.height * 0.02)
            }.clipShape(RoundedRectangle(cornerRadius: 30))
        }.accessibilityHidden(true)
    }
}

private struct CuadraoChartWave: Shape {
    let crest: CGFloat
    func path(in rect: CGRect) -> Path {
        Path { path in
            path.move(to: CGPoint(x: 0, y: rect.height * (0.4 + crest)))
            path.addCurve(to: CGPoint(x: rect.maxX, y: rect.height * 0.3),
                control1: CGPoint(x: rect.width * 0.4, y: -rect.height * 0.7),
                control2: CGPoint(x: rect.width * 0.7, y: rect.height))
            path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
            path.addLine(to: CGPoint(x: 0, y: rect.maxY)); path.closeSubpath()
        }
    }
}

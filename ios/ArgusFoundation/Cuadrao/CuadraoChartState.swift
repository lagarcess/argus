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
                    PlanLandscape(look: .coast).frame(width: 84, height: 76).offset(x: 4, y: 12)
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

import SwiftUI

struct CuadraoHomeInsightsLayout<Content: View>: View {
    let spanish: Bool
    @Binding var range: CanvasHistoryRange
    @Binding var periodOffset: Int
    @Binding var distribution: Bool
    @Binding var activity: Bool
    let oldestOffset: (Bool) -> Int
    @ViewBuilder let content: (Int) -> Content

    private var oldest: Int { oldestOffset(activity) }
    private func movePeriod(_ direction: Int) {
        periodOffset = min(0, max(oldest, periodOffset + direction))
    }
    private var metricChoice: some View {
        CuadraoChoiceMenu(title: spanish ? "Vista" : "View", selection: Binding(get: { activity }, set: { value in
            periodOffset = max(oldestOffset(value), periodOffset)
            activity = value
        }), values: [false, true], valueTitle: { value in
            value ? (spanish ? "Actividad" : "Activity") : "Balance"
        }).accessibilityIdentifier("home-insight-metric")
    }

    var body: some View {
        VStack(spacing: 8) {
            VStack(spacing: 4) {
                metricChoice.frame(maxWidth: .infinity, alignment: .trailing)
                CuadraoInsightControls(range: Binding(get: { range }, set: { periodOffset = 0; range = $0 }),
                    distribution: $distribution, spanish: spanish, activity: activity)
            }.padding(.horizontal, 24)
            TabView(selection: $periodOffset) {
                ForEach(Array(oldest...0), id: \.self) { offset in
                    ScrollView {
                        if abs(offset - periodOffset) <= 1 {
                            VStack(alignment: .leading, spacing: 16) {
                                Text(range.periodLabel(spanish: spanish, offset: offset))
                                    .font(CuadraoTypography.feature).foregroundStyle(WelcomePalette.ink)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .accessibilityIdentifier("home-insight-period")
                                content(offset)
                            }.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 32)
                        }
                    }
                    .accessibilityIdentifier("home-insights-content")
                    .accessibilityHidden(offset != periodOffset)
                    .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
                    .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
                    .tag(offset)
                }
            }.tabViewStyle(.page(indexDisplayMode: .never)).id(range.rawValue + String(activity))
                .accessibilityAction(named: Text(spanish ? "Período anterior" : "Previous period")) { movePeriod(-1) }
                .accessibilityAction(named: Text(spanish ? "Período siguiente" : "Next period")) { movePeriod(1) }
        }.onChange(of: oldest) { _, value in periodOffset = max(value, periodOffset) }
    }
}

struct CuadraoHomeInsightsChrome: ViewModifier {
    let title: String
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss

    func body(content: Content) -> some View {
        content.background(WelcomePalette.background)
            .navigationTitle(title).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { dismiss() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                        .accessibilityLabel(spanish ? "Cerrar" : "Close")
                        .accessibilityIdentifier("home-history-done")
                }
            }
    }
}

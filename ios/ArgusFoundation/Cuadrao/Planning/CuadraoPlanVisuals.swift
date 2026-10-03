import SwiftUI
import Charts

extension CanvasPlanLook {
    var color: Color {
        switch self {
        case .coast: WelcomePalette.pine
        case .sunshine: WelcomePalette.sunshine
        case .bloom: WelcomePalette.bloom
        case .clay: WelcomePalette.clay
        }
    }
}

enum PlanFormat {
    static func amount(_ value: Double, currency: String = "DOP") -> String {
        let number = value.formatted(.number.precision(.fractionLength(0...2)).locale(Locale(identifier: "en_US")))
        return "\(currency) \(number)"
    }
    static func month(after count: Int, spanish: Bool) -> String {
        let date = Calendar.current.date(from: DateComponents(year: 2026, month: 10 + count, day: 12))!
        let text = date.formatted(.dateTime.month(.wide).year().locale(Locale(identifier: spanish ? "es_DO" : "en_US")))
        return text.prefix(1).uppercased() + text.dropFirst()
    }
    static func space(_ id: String, accounts: CuadraoAccountsPreview, spanish: Bool) -> String {
        accounts.spaces.first { $0.id == id }?.title(spanish) ?? (spanish ? "Espacio archivado" : "Archived space")
    }
}

struct PlanPrimaryButton: View {
    let title: String
    var symbol: String? = nil
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Text(title)
                if let symbol { Image(systemName: symbol) }
            }.font(CuadraoTypography.action).frame(maxWidth: .infinity, minHeight: 52)
                .foregroundStyle(WelcomePalette.onAccent)
                .background(WelcomePalette.pine, in: Capsule())
        }.buttonStyle(.plain)
    }
}

/// Quiet, scalable cover art, drawn natively instead of decorative stock imagery.
struct PlanLandscape: View {
    let look: CanvasPlanLook
    var body: some View {
        GeometryReader { g in
            ZStack {
                Circle().fill(look.color.opacity(0.10)).frame(width: g.size.width * 0.8)
                Circle().fill(look.color.opacity(0.24))
                    .frame(width: g.size.width * 0.29, height: g.size.width * 0.29)
                    .offset(x: g.size.width * 0.16, y: -g.size.height * 0.19)
                ForEach(0..<3) { index in
                    PlanWave(crest: CGFloat(index) * 0.12)
                        .fill(look.color.opacity(0.12 + Double(index) * 0.09))
                        .frame(height: g.size.height * 0.5)
                        .offset(y: g.size.height * 0.15 + CGFloat(index) * 9)
                }
                Image(systemName: look.symbol).font(.system(size: 27, weight: .light))
                    .foregroundStyle(look.color).offset(x: -g.size.width * 0.13, y: g.size.height * 0.02)
            }.clipShape(RoundedRectangle(cornerRadius: 30))
        }.accessibilityHidden(true)
    }
}

private struct PlanWave: Shape {
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

struct PlanCard: View {
    let plan: CanvasPlan
    let space: String
    let spanish: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(space).font(.caption).foregroundStyle(.secondary)
                    Text(plan.name).font(CuadraoTypography.section).foregroundStyle(WelcomePalette.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
                PlanLandscape(look: plan.look).frame(width: 84, height: 84)
            }
            VStack(alignment: .leading, spacing: 9) {
                HStack(alignment: .firstTextBaseline) {
                    Text(PlanFormat.amount(plan.kind == .debt ? plan.remaining : plan.recorded, currency: plan.currency))
                        .font(CuadraoTypography.secondaryAmount)
                    Spacer(minLength: 8)
                    Text(plan.kind == .debt ? (spanish ? "por pagar" : "to go") : "\(Int(plan.recorded / max(plan.target, 1) * 100))%")
                        .font(.caption).foregroundStyle(.secondary)
                }
                GeometryReader { g in
                    Capsule().fill(plan.look.color.opacity(0.1))
                        .overlay(alignment: .leading) {
                            Capsule().fill(plan.look.color).frame(width: max(0, g.size.width * plan.progress))
                        }
                }.frame(height: 4).accessibilityHidden(true)
                Text(plan.kind == .budget
                     ? (spanish ? "de \(PlanFormat.amount(plan.target, currency: plan.currency)) este mes" : "of \(PlanFormat.amount(plan.target, currency: plan.currency)) this month")
                     : (spanish ? "\(plan.kind == .debt ? "Deuda inicial" : "Meta"): \(PlanFormat.amount(plan.target, currency: plan.currency))" : "\(plan.kind == .debt ? "Starting debt" : "Goal"): \(PlanFormat.amount(plan.target, currency: plan.currency))"))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }.padding(22).frame(maxWidth: .infinity, alignment: .leading)
            .background(plan.look.color.opacity(0.065), in: RoundedRectangle(cornerRadius: 28))
            .contentShape(RoundedRectangle(cornerRadius: 28))
    }
}

struct PlanForecastChart: View {
    let forecast: CanvasForecast
    let daily: Double
    let spanish: Bool
    var comparison: Double? = nil
    @Binding var selectedDay: Int?
    var detailed = false
    var compact = false
    var selected: CanvasForecastPoint? {
        guard let selectedDay else { return nil }
        return (forecast.actual + forecast.projection(daily: daily).dropFirst()).first { $0.day == selectedDay }
    }
    var body: some View {
        Chart {
            ForEach(forecast.actual) { point in
                AreaMark(x: .value("Day", point.day), y: .value("Balance", point.balance))
                    .foregroundStyle(LinearGradient(colors: [WelcomePalette.pine.opacity(0.13), .clear], startPoint: .top, endPoint: .bottom))
                LineMark(x: .value("Day", point.day), y: .value("Balance", point.balance), series: .value("Path", "actual"))
                    .foregroundStyle(WelcomePalette.pine).lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .interpolationMethod(.linear)
            }
            if let comparison, comparison != daily {
                ForEach(forecast.projection(daily: comparison)) { point in
                    LineMark(x: .value("Day", point.day), y: .value("Balance", point.balance), series: .value("Path", "baseline"))
                        .foregroundStyle(Color.secondary.opacity(0.3)).lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 5]))
                }
            }
            ForEach(forecast.projection(daily: daily)) { point in
                LineMark(x: .value("Day", point.day), y: .value("Balance", point.balance), series: .value("Path", "forecast"))
                    .foregroundStyle(WelcomePalette.pine).lineStyle(StrokeStyle(lineWidth: 2.5, lineCap: .round, dash: [5, 5]))
            }
            RuleMark(x: .value("Today", CanvasForecast.today))
                .foregroundStyle(Color.secondary.opacity(0.25)).lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))
            if detailed {
                RuleMark(y: .value("Zero", 0)).foregroundStyle(Color.secondary.opacity(0.18))
            }
            if let point = selected {
                RuleMark(x: .value("Selected", point.day)).foregroundStyle(WelcomePalette.pine.opacity(0.4))
                PointMark(x: .value("Day", point.day), y: .value("Balance", point.balance))
                    .foregroundStyle(WelcomePalette.pine).symbolSize(45)
            }
        }
        .chartXScale(domain: 1...31)
        .chartYScale(domain: -30000...65000)
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: [1, 12, 31]) { value in
                AxisValueLabel(anchor: value.as(Int.self) == 31 ? .topTrailing : value.as(Int.self) == 1 ? .topLeading : .top, collisionResolution: .disabled) {
                    if let day = value.as(Int.self) {
                        Text(day == 12 ? (spanish ? "Hoy, 12" : "Today, 12") : "\(day) oct.").font(.caption2)
                    }
                }
            }
        }
        .chartXSelection(value: $selectedDay)
        .accessibilityIdentifier("plan-forecast-chart")
        .frame(height: compact ? 95 : detailed ? 170 : 150)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spanish ? "Balance de octubre. Línea continua: registrado. Línea punteada: estimación." : "October balance. Solid line: recorded. Dashed line: estimate.")
        .accessibilityValue(PlanFormat.amount(forecast.ending(daily: daily)))
    }
}

struct PlanPreviewFootnote: View {
    let spanish: Bool
    var body: some View {
        Text(spanish ? "Vista previa · datos de ejemplo" : "Preview · example data")
            .font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity).padding(.vertical, 12)
    }
}

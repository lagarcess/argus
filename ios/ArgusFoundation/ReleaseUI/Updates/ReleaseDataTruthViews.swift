import SwiftUI

struct ReleaseMonthComparison: View {
    let current: ReleaseRecordedMonth
    let previous: ReleaseRecordedMonth
    let currency: String
    let spanish: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            switch current {
            case .missingCoverage:
                Text(CuadraoMissingCoverage.amount(spanish)).font(CuadraoTypography.secondaryAmount)
                Text(CuadraoMissingCoverage.detail(spanish))
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
            case .recorded(let amount):
                Text(currency + " " + CanvasMoney.format(amount, currency: currency)).font(CuadraoTypography.secondaryAmount)
            }
            switch current.compared(to: previous) {
            case .unavailable: EmptyView()
            case .amount(let difference):
                Text(spanish ? "Diferencia frente al mes anterior: \(signed(difference))." : "Difference from last month: \(signed(difference)).")
                    .font(CuadraoTypography.supporting)
            case .percentage(let percent):
                Text((percent > 0 ? "+" : "") + percent.formatted(.number.precision(.fractionLength(1))
                    .locale(Locale(identifier: spanish ? "es_DO" : "en_US"))) + "% " + (spanish ? "frente al mes anterior" : "from last month"))
                    .font(CuadraoTypography.supporting)
            }
        }.accessibilityElement(children: .combine).accessibilityIdentifier("release-month-comparison")
    }
    private func signed(_ amount: Decimal) -> String {
        (amount > 0 ? "+" : "") + currency + " " + CanvasMoney.format(amount, currency: currency)
    }
}

struct ReleaseHistoryAccessNote: View {
    let access: ReleaseHistoryAccess
    let spanish: Bool
    var body: some View {
        switch access {
        case .editable: EmptyView()
        case .readOnly:
            Label(spanish ? "Solo lectura" : "Read-only", systemImage: "lock")
                .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
        case .movedOutOfHousehold:
            Label {
                VStack(alignment: .leading, spacing: 5) {
                    Text(spanish ? "Historial de solo lectura" : "Read-only history")
                    Text(spanish ? "La cuenta se movió fuera del hogar. Aquí se conserva el historial anterior; no se añaden movimientos nuevos."
                        : "The account moved out of the household. Earlier history stays here; new activity is not added.")
                }
            } icon: { Image(systemName: "clock.arrow.circlepath") }
                .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                .accessibilityIdentifier("release-moved-history-note")
        }
    }
}

struct ReleaseHistoryRecordRow: View {
    let title: String
    let amount: Decimal
    let currency: String
    let date: Date
    let access: ReleaseHistoryAccess
    let spanish: Bool
    private var moved: Bool { if case .movedOutOfHousehold = access { return true }; return false }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(title).font(CuadraoTypography.body)
                    Text(date.formatted(.dateTime.month(.abbreviated).day().year()
                        .locale(Locale(identifier: spanish ? "es_DO" : "en_US"))))
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 12)
                Text(currency + " " + CanvasMoney.format(amount, currency: currency)).font(CuadraoTypography.rowAmount)
            }.foregroundStyle(moved ? Color.secondary : WelcomePalette.ink)
            ReleaseHistoryAccessNote(access: access, spanish: spanish)
        }.accessibilityElement(children: .combine).accessibilityIdentifier("release-history-record")
    }
}

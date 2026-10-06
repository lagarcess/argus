import Foundation

@main enum CurrencyPresentationChecks {
    struct Row: Equatable {
        let currency: String
        let minor: String?
        let digits: Int
        let unknownCount: Int
        let authorizedAccountIDs: [String]
    }

    static func main() {
        let rows = [
            Row(currency: "USD", minor: "9007199254740993", digits: 2, unknownCount: 1, authorizedAccountIDs: ["shared-usd"]),
            Row(currency: "JPY", minor: "0", digits: 0, unknownCount: 0, authorizedAccountIDs: ["shared-jpy"]),
            Row(currency: "KWD", minor: nil, digits: 3, unknownCount: 2, authorizedAccountIDs: ["shared-kwd"])
        ]
        let cases: [(String?, [String])] = [
            (nil, ["JPY", "KWD", "USD"]),
            ("EUR", ["JPY", "KWD", "USD"]),
            ("USD", ["USD", "JPY", "KWD"]),
            ("KWD", ["KWD", "JPY", "USD"])
        ]
        for (primary, expected) in cases {
            let result = CurrencyPresentation.ordered(rows, primary: primary, currency: { $0.currency })
            precondition(result.map(\.currency) == expected)
            precondition(result.count == rows.count)
            for row in rows { precondition(result.first { $0.currency == row.currency } == row) }
        }
        let empty: [Row] = []
        precondition(CurrencyPresentation.ordered(empty, primary: "DOP", currency: { $0.currency }).isEmpty)
        let authorized = rows.filter { $0.currency != "USD" }
        precondition(CurrencyPresentation.ordered(authorized, primary: "USD", currency: { $0.currency }) == [rows[1], rows[2]])
        let zero = CurrencyPresentation.ordered([rows[1]], primary: nil, currency: { $0.currency })
        precondition(zero == [rows[1]] && zero[0].minor == "0")
        let unknown = CurrencyPresentation.ordered([rows[2]], primary: "KWD", currency: { $0.currency })
        precondition(unknown == [rows[2]] && unknown[0].minor == nil)
        let firstProfile = CurrencyPresentation.ordered(rows, primary: "USD", currency: { $0.currency })
        let switchedProfile = CurrencyPresentation.ordered(rows, primary: "JPY", currency: { $0.currency })
        precondition(firstProfile.first == rows[0] && switchedProfile.first == rows[1])
        let selectionCases: [(String?, String?, String?)] = [
            (nil, nil, nil), (nil, "EUR", nil), (nil, "USD", "USD"),
            ("JPY", "USD", "JPY"), ("KWD", "USD", "KWD"),
            ("EUR", "USD", "USD"), ("EUR", nil, nil)
        ]
        for (explicit, primary, expected) in selectionCases {
            let code = CurrencyPresentation.selectedCode(available: rows.map(\.currency), explicit: explicit, primary: primary)
            precondition(code == expected)
            let selectedRows = rows.filter { $0.currency == code }
            precondition(selectedRows.count == (expected == nil ? 0 : 1))
            if let selected = selectedRows.first {
                precondition(rows.contains(selected))
            }
        }
        precondition(CurrencyPresentation.selectedCode(available: [], explicit: "USD", primary: "USD") == nil)
        precondition(CurrencyPresentation.selectedCode(available: ["JPY"], explicit: nil, primary: "USD") == "JPY")
        precondition(CurrencyPresentation.selectedCode(available: authorized.map(\.currency), explicit: "USD", primary: "USD") == nil)
        let explicitUnknown = CurrencyPresentation.selectedCode(available: rows.map(\.currency), explicit: "KWD", primary: "USD")
        precondition(rows.first { $0.currency == explicitUnknown } == rows[2])
        let following = CurrencyPresentation.selectedCode(available: rows.map(\.currency), explicit: nil, primary: "JPY")
        let retained = CurrencyPresentation.selectedCode(available: rows.map(\.currency), explicit: "USD", primary: "JPY")
        precondition(following == "JPY" && retained == "USD")
        print("Currency ordering, forecast selection and authorized payload preservation checks passed")
    }
}

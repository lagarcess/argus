import SwiftUI
import UIKit

struct CuadraoAmountField: View {
    @Binding var raw: String
    @Binding var currency: String
    @Binding var error: String
    let spanish: Bool
    var allowNegative = false
    var currencySelectable = true
    @State private var choosingCurrency = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Button { choosingCurrency = true } label: {
                    HStack(spacing: 7) {
                        Text(currency).font(.title3)
                        if currencySelectable { Image(systemName: "chevron.down").font(.caption) }
                    }.foregroundStyle(.secondary).frame(minHeight: 56)
                }.disabled(!currencySelectable)
                    .accessibilityLabel(spanish ? "Moneda, \(currency)" : "Currency, \(currency)")
                CanvasDecimalInput(raw: $raw, error: $error, currency: currency,
                    spanish: spanish, allowNegative: allowNegative)
                    .frame(minHeight: 60)
            }
            .padding(.horizontal, 18).padding(.vertical, 4)
            .background(WelcomePalette.background, in: RoundedRectangle(cornerRadius: 18))
            .overlay { RoundedRectangle(cornerRadius: 18).stroke(error.isEmpty ? WelcomePalette.border : .red.opacity(0.7)) }
            if !error.isEmpty { Text(error).font(.footnote).foregroundStyle(.red).accessibilityIdentifier("amount-error") }
        }
        .sheet(isPresented: $choosingCurrency) {
            CanvasCurrencyPicker(currency: $currency, spanish: spanish)
        }
        .onChange(of: currency) { _, _ in
            let fraction = raw.split(separator: ".", omittingEmptySubsequences: false).dropFirst().first?.count ?? 0
            error = fraction > CanvasMoney.digits(currency)
                ? (spanish ? "Revisa los decimales para \(currency)." : "Check decimal places for \(currency).") : ""
        }
    }
}

private struct CanvasCurrencyPicker: View {
    @Binding var currency: String
    let spanish: Bool
    @State private var query = ""
    @Environment(\.dismiss) private var dismiss
    private var codes: [String] {
        let priority = ["DOP", "USD", "EUR"]
        let all = priority + Locale.commonISOCurrencyCodes.filter { !priority.contains($0) }.sorted()
        return all.filter { query.isEmpty || $0.localizedCaseInsensitiveContains(query) || name($0).localizedCaseInsensitiveContains(query) }
    }
    private func name(_ code: String) -> String {
        Locale(identifier: spanish ? "es_DO" : "en_US").localizedString(forCurrencyCode: code) ?? code
    }
    var body: some View {
        NavigationStack {
            List(codes, id: \.self) { code in
                Button {
                    currency = code; dismiss()
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(code).foregroundStyle(.primary)
                            Text(name(code)).font(.subheadline).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if code == currency { Image(systemName: "checkmark") }
                    }.padding(.vertical, 4)
                }
            }.listStyle(.plain)
                .searchable(text: $query, prompt: spanish ? "Nombre o código" : "Name or code")
                .navigationTitle(spanish ? "Moneda" : "Currency").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(spanish ? "Listo" : "Done") { dismiss() } } }
        }.tint(WelcomePalette.pine)
    }
}

/// Native editable text keeps selection and the caret while adding grouping separators.
private struct CanvasDecimalInput: UIViewRepresentable {
    @Binding var raw: String
    @Binding var error: String
    let currency: String
    let spanish: Bool
    let allowNegative: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.delegate = context.coordinator
        field.keyboardType = .decimalPad
        field.textAlignment = .right
        field.font = UIFontMetrics(forTextStyle: .title1).scaledFont(for: .monospacedDigitSystemFont(ofSize: 30, weight: .regular))
        field.adjustsFontForContentSizeCategory = true
        field.adjustsFontSizeToFitWidth = true; field.minimumFontSize = 17
        field.backgroundColor = .clear
        field.accessibilityIdentifier = "cuadrao-amount"
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let toolbar = UIToolbar(); toolbar.sizeToFit()
        toolbar.items = [UIBarButtonItem(systemItem: .flexibleSpace),
            UIBarButtonItem(title: spanish ? "Listo" : "Done", style: .done,
                target: context.coordinator, action: #selector(Coordinator.done))]
        field.inputAccessoryView = toolbar
        context.coordinator.field = field
        return field
    }
    func updateUIView(_ field: UITextField, context: Context) {
        context.coordinator.parent = self
        let current = (field.text ?? "").replacingOccurrences(of: ",", with: "")
        if current != raw { field.text = Coordinator.group(raw) }
        field.placeholder = CanvasMoney.format(0, currency: currency)
        field.accessibilityLabel = spanish ? "Monto" : "Amount"
        field.textColor = (Decimal(string: raw) ?? 0) > 0
            ? UIColor(red: 0.18, green: 0.47, blue: 0.40, alpha: 1) : .secondaryLabel
    }
    final class Coordinator: NSObject, UITextFieldDelegate {
        var parent: CanvasDecimalInput
        weak var field: UITextField?
        init(_ parent: CanvasDecimalInput) { self.parent = parent }
        @objc func done() { field?.resignFirstResponder() }
        func textField(_ textField: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
            let old = textField.text ?? ""
            guard let r = Range(range, in: old) else { return false }
            var proposed = old.replacingCharacters(in: r, with: string)
            var logical = old[..<r.lowerBound].filter { $0 != "," }.count + string.filter { $0 != "," }.count
            if string.isEmpty, old[r] == ",", range.location > 0 {
                let deletion = NSRange(location: range.location - 1, length: range.length + 1)
                if let deletionRange = Range(deletion, in: old) {
                    proposed = old.replacingCharacters(in: deletionRange, with: ""); logical -= 1
                }
            }
            if string.count > 1 && string.contains(",") &&
                string.range(of: #"^-?(?:[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]*)?$"#, options: .regularExpression) == nil {
                parent.error = parent.spanish ? "Revisa las comas del monto." : "Check the amount’s grouping."; return false
            }
            var normalized = proposed.replacingOccurrences(of: ",", with: "")
            let pattern = parent.allowNegative ? #"^-?[0-9]*(?:\.[0-9]*)?$"# : #"^[0-9]*(?:\.[0-9]*)?$"#
            guard normalized.range(of: pattern, options: .regularExpression) != nil else {
                parent.error = parent.spanish ? "Usa números y un punto decimal." : "Use digits and a decimal point."; return false
            }
            if normalized.hasPrefix(".") { normalized = "0" + normalized; logical += 1 }
            let fraction = normalized.split(separator: ".", omittingEmptySubsequences: false).dropFirst().first?.count ?? 0
            guard fraction <= CanvasMoney.digits(parent.currency) else {
                parent.error = parent.spanish ? "Revisa los decimales para \(parent.currency)." : "Check decimal places for \(parent.currency)."; return false
            }
            guard abs(Decimal(string: normalized) ?? 0) <= CanvasMoney.maximum, normalized.count <= 24 else {
                parent.error = parent.spanish ? "Máximo: 9,999,999.99" : "Maximum: 9,999,999.99"; return false
            }
            parent.error = ""; parent.raw = normalized
            let grouped = Self.group(normalized)
            textField.text = grouped
            var location = 0, count = 0
            for char in grouped {
                if count >= logical { break }
                location += 1; if char != "," { count += 1 }
            }
            if let position = textField.position(from: textField.beginningOfDocument, offset: location) {
                textField.selectedTextRange = textField.textRange(from: position, to: position)
            }
            if old.filter({ $0 == "," }).count != grouped.filter({ $0 == "," }).count && !UIAccessibility.isReduceMotionEnabled {
                let transition = CATransition(); transition.type = .fade; transition.duration = 0.12
                textField.layer.add(transition, forKey: "grouping")
            }
            return false
        }
        func textFieldDidEndEditing(_ textField: UITextField) {
            guard let value = Decimal(string: parent.raw), !parent.raw.isEmpty else { return }
            let fraction = parent.raw.split(separator: ".", omittingEmptySubsequences: false).dropFirst().first?.count ?? 0
            guard fraction <= CanvasMoney.digits(parent.currency) else { return }
            let formatted = CanvasMoney.format(value, currency: parent.currency)
            parent.raw = formatted.replacingOccurrences(of: ",", with: "")
            textField.text = formatted
        }
        static func group(_ raw: String) -> String {
            let parts = raw.split(separator: ".", omittingEmptySubsequences: false)
            guard let first = parts.first else { return "" }
            let negative = first.hasPrefix("-")
            let digits = negative ? String(first.dropFirst()) : String(first)
            let grouped = String(digits.reversed().enumerated().map { i, ch in
                (i > 0 && i % 3 == 0 ? "," : "") + String(ch)
            }.joined().reversed())
            return (negative ? "-" : "") + grouped + (parts.count > 1 ? "." + parts[1] : "")
        }
    }
}

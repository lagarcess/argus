import SwiftUI
import UIKit

/// Roles shared by every design surface. Screen-specific layouts stay local.
enum CuadraoTypography {
    static let screen = Font.system(.largeTitle, design: .serif)
    static let feature = Font.system(.title, design: .serif)
    static let section = Font.system(.title2, design: .serif)
    static let body = Font.body
    static let supporting = Font.subheadline
    static let caption = Font.caption
    static let action = Font.body.weight(.medium)
    static let rowAmount = Font.system(.subheadline, design: .rounded).weight(.medium).monospacedDigit()
    static let amount = Font.system(.largeTitle, design: .rounded).weight(.medium).monospacedDigit()
    static let secondaryAmount = Font.system(.title2, design: .rounded).weight(.medium).monospacedDigit()

    enum MoneySize { case prominent, secondary, row }
    static func moneyFont(_ size: MoneySize, category: UIContentSizeCategory) -> UIFont {
        let style: UIFont.TextStyle = size == .prominent ? .largeTitle : size == .secondary ? .title2 : .subheadline
        let base = UIFont.preferredFont(forTextStyle: style, compatibleWith: UITraitCollection(preferredContentSizeCategory: .large))
        let digits = UIFont.monospacedDigitSystemFont(ofSize: base.pointSize, weight: .medium)
        let rounded = UIFont(descriptor: digits.fontDescriptor.withDesign(.rounded) ?? digits.fontDescriptor, size: base.pointSize)
        return UIFontMetrics(forTextStyle: style).scaledFont(for: rounded, compatibleWith: UITraitCollection(preferredContentSizeCategory: category))
    }
}

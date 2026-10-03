import SwiftUI

struct RegistrationHeading: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title)
                .font(CuadraoTypography.screen)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text(detail)
                .font(.body)
                .foregroundStyle(.secondary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct RegistrationButton: View {
    let title: String
    var busy = false
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy { ProgressView().tint(WelcomePalette.onAccent) }
                Text(title)
            }
            .font(.system(.body, weight: .semibold))
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(enabled || busy ? WelcomePalette.onAccent : WelcomePalette.disabledInk)
            .background(enabled || busy ? WelcomePalette.pine : WelcomePalette.sage,
                        in: RoundedRectangle(cornerRadius: 16))
            .contentShape(RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
        .disabled(!enabled || busy)
    }
}

struct RegistrationField: ViewModifier {
    var focused = false
    var invalid = false

    func body(content: Content) -> some View {
        content
            .padding(.horizontal, 16)
            .frame(minHeight: 58)
            .background(WelcomePalette.background, in: RoundedRectangle(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(invalid ? Color.red : focused ? WelcomePalette.pine : WelcomePalette.border,
                            lineWidth: focused || invalid ? 1.5 : 1)
            }
    }
}

struct RegistrationNotice: View {
    var symbol = "wifi.exclamationmark"
    let title: String
    let detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: symbol)
                .font(.body)
                .padding(.top, 2)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(detail).font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
    }
}

/// Input feedback for the disconnected design preview, not an auth policy.
enum PreviewEmail {
    static func normalized(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    static func isValid(_ value: String) -> Bool {
        let email = normalized(value)
        let parts = email.split(separator: "@", omittingEmptySubsequences: false)
        return parts.count == 2 && !parts[0].isEmpty && parts[1].contains(".")
            && !parts[1].hasPrefix(".") && !parts[1].hasSuffix(".")
            && !email.contains(where: { $0.isWhitespace })
    }
}

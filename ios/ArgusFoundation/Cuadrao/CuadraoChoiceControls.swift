import SwiftUI

/// One label grammar for single-choice menus and searchable pickers.
struct CuadraoChoiceLabel: View {
    let title: String
    var selectable = true
    var locked = false
    var body: some View {
        HStack(spacing: 6) {
            Text(title).font(CuadraoTypography.supporting)
            if selectable || locked {
                Image(systemName: selectable ? "chevron.down" : "lock")
                    .font(.caption2.weight(.semibold)).accessibilityHidden(true)
            }
        }.foregroundStyle(selectable ? WelcomePalette.pine : WelcomePalette.ink.opacity(0.6))
            .frame(minHeight: 44).contentShape(Rectangle())
    }
}

struct CuadraoChoiceOption: View {
    let title: String
    let selected: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            if selected { Label(title, systemImage: "checkmark") }
            else { Text(title) }
        }
    }
}

struct CuadraoSectionAddButton: View {
    let title: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: "plus").font(.body.weight(.medium))
                .frame(width: 44, height: 44).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityLabel(title)
    }
}

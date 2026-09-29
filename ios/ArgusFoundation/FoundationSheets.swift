import SwiftUI

struct FoundationSheetView: View {
    let sheet: FoundationSheet
    @Binding var appearance: AppearancePreference
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if sheet == .profile {
                    profile
                } else {
                    SamplePage {
                        Text(sheet.title).font(ArgusStyle.display())
                        Text(LocalizedStringKey("sheet." + sheet.rawValue + ".detail"))
                            .foregroundStyle(ArgusStyle.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .background(ArgusStyle.background)
            .navigationTitle(sheet.title)
            .navigationBarTitleDisplayMode(.inline)
            .modifier(SheetCloseToolbar(close: { dismiss() }))
        }
        .presentationDragIndicator(.visible)
    }

    private var profile: some View {
        SamplePage {
            Text("profile.local").font(ArgusStyle.display(24, relativeTo: .title2))
            Text("profile.app").font(ArgusStyle.body(12, relativeTo: .caption))
                .foregroundStyle(ArgusStyle.secondary)
                .accessibilityAddTraits(.isHeader)
            NavigationLink {
                AppearancePreferencesView(appearance: $appearance)
                    .modifier(SheetCloseToolbar(close: { dismiss() }))
            } label: {
                SampleRow(title: "profile.preferences", subtitle: "profile.preferences.detail", symbol: "paintpalette")
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("profile.preferences")
            Text("profile.scope")
                .font(ArgusStyle.body(14, relativeTo: .subheadline))
                .foregroundStyle(ArgusStyle.secondary)
        }
    }
}

struct AppearancePreferencesView: View {
    @Binding var appearance: AppearancePreference
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        SamplePage {
            Text("appearance.title").font(ArgusStyle.display(24, relativeTo: .title2))
                .accessibilityAddTraits(.isHeader)
            VStack(spacing: 0) {
                ForEach(AppearancePreference.allCases, id: \.self) { preference in
                    Button { appearance = preference } label: {
                        HStack(spacing: 16) {
                            Text(preference.title).font(ArgusStyle.body())
                            Spacer()
                            Image(systemName: appearance == preference ? "checkmark.circle.fill" : "circle")
                                .accessibilityHidden(true)
                        }
                        .padding(.vertical, 16)
                        .frame(minHeight: 48)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("appearance.\(preference.rawValue)")
                    .accessibilityAddTraits(appearance == preference ? .isSelected : [])
                    .accessibilityValue(appearance == preference ? Text("appearance.selected") : Text("appearance.unselected"))
                    Divider().overlay(ArgusStyle.line)
                }
            }
            Text("appearance.detail")
                .font(ArgusStyle.body(14, relativeTo: .subheadline))
                .foregroundStyle(ArgusStyle.secondary)
            Text(scheme == .dark ? "appearance.current.dark" : "appearance.current.light")
                .font(ArgusStyle.body(12, relativeTo: .caption))
                .foregroundStyle(ArgusStyle.secondary)
                .accessibilityIdentifier("appearance.resolved")
                .accessibilityValue(scheme == .dark ? "dark" : "light")
        }
        .background(ArgusStyle.background)
        .navigationTitle("profile.preferences")
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.preferences")
    }
}

private struct SheetCloseToolbar: ViewModifier {
    let close: () -> Void

    func body(content: Content) -> some View {
        content.toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("action.close", action: close)
                    .accessibilityIdentifier("sheet.close")
            }
        }
    }
}

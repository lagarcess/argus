import SwiftUI

enum CanvasProfileAvatarStyle: Equatable {
    case initial
    case theme(CanvasPlanLook)
}

struct CanvasProfileAvatar: View {
    let name: String
    let style: CanvasProfileAvatarStyle
    var size: CGFloat = 64

    var body: some View {
        Group {
            switch style {
            case .initial:
                Text(String(name.trimmingCharacters(in: .whitespacesAndNewlines).prefix(1)).uppercased())
                    .frame(width: size, height: size)
                    .foregroundStyle(WelcomePalette.pine).background(WelcomePalette.sage)
            case .theme(let theme):
                Image(systemName: theme.symbol).frame(width: size, height: size)
                    .foregroundStyle(theme.color).background(theme.color.opacity(0.12))
            }
        }.font(.system(.title, design: .rounded, weight: .medium))
            .frame(width: size, height: size).clipShape(Circle()).accessibilityHidden(true)
    }
}

/// Release rule (fc7650ea): identity uses initials and the existing avatar themes.
/// Personal photo selection, crop, replacement and upload stay hidden.
struct CuadraoProfileAvatarPicker: View {
    let name: String
    let spanish: Bool
    @Binding var avatar: CanvasProfileAvatarStyle

    var body: some View {
        Section {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 76))], spacing: 12) {
                choice(nil)
                ForEach(CanvasPlanLook.allCases) { choice($0) }
            }.padding(.vertical, 8)
        } header: { Text(spanish ? "Tu avatar" : "Your avatar") }
            .listRowBackground(CanvasSettingsStyle.surface)
    }

    private func select(_ style: CanvasProfileAvatarStyle) { avatar = style }

    private func choice(_ theme: CanvasPlanLook?) -> some View {
        let style = theme.map(CanvasProfileAvatarStyle.theme) ?? .initial
        let title = theme?.title(spanish) ?? (spanish ? "Inicial" : "Initial")
        return Button { select(style) } label: {
            VStack(spacing: 6) {
                CanvasProfileAvatar(name: name, style: style)
                    .overlay(alignment: .bottomTrailing) {
                        if avatar == style {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(WelcomePalette.pine, WelcomePalette.background)
                        }
                    }
                Text(title).font(.caption).foregroundStyle(.primary)
            }.frame(minHeight: 88)
        }.buttonStyle(.plain).accessibilityLabel(title)
            .accessibilityAddTraits(avatar == style ? .isSelected : [])
            .accessibilityIdentifier("cuadrao.profile.avatar.\(theme?.rawValue ?? "initial")")
    }
}

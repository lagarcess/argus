import SwiftUI

/// Visual exploration only. Does not replace the shipped Argus theme.
enum Cuadrao {
    static let paper = color(0xF4F1EA)
    static let raised = color(0xFBF9F5)
    static let sand = color(0xE6DFD4)
    static let line = color(0xD4CBBC)
    static let ink = color(0x141716)
    static let muted = color(0x5C574F)
    static let pine = color(0x1C3830)

    static func color(_ value: UInt32) -> Color {
        Color(red: Double(value >> 16 & 255) / 255,
              green: Double(value >> 8 & 255) / 255, blue: Double(value & 255) / 255)
    }

    static func text(_ size: CGFloat = 15) -> Font {
        .custom("Inter-Regular", size: size, relativeTo: .body)
    }

    static func title(_ size: CGFloat = 30) -> Font {
        .custom("IowanOldStyle-Roman", size: size, relativeTo: .title)
    }

    static func money(_ cents: Int) -> String {
        (Double(cents) / 100).formatted(.number.precision(.fractionLength(2)))
    }
}

struct CuadraoPrimaryButton: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Cuadrao.text()).fontWeight(.medium)
            .frame(maxWidth: .infinity, minHeight: 52)
            .foregroundStyle(enabled ? Cuadrao.paper : Cuadrao.muted)
            .background(enabled ? Cuadrao.pine : Cuadrao.sand,
                        in: RoundedRectangle(cornerRadius: 10))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct CuadraoSymbol: View {
    let name: String
    var body: some View {
        Image(systemName: name).font(.system(size: 19, weight: .regular))
            .foregroundStyle(Cuadrao.pine)
            .frame(width: 44, height: 44)
            .background(Cuadrao.sand.opacity(0.6), in: RoundedRectangle(cornerRadius: 12))
            .accessibilityHidden(true)
    }
}

struct CuadraoMark: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 4).frame(width: 15, height: 15).offset(x: 4, y: -4)
            RoundedRectangle(cornerRadius: 4).frame(width: 15, height: 15).offset(x: -4, y: 4)
        }
        .foregroundStyle(Cuadrao.paper)
        .frame(width: 40, height: 40)
        .background(Cuadrao.pine, in: RoundedRectangle(cornerRadius: 11))
        .accessibilityHidden(true)
    }
}

struct CuadraoSectionTitle: View {
    let title: String
    var body: some View {
        Text(title).font(Cuadrao.title(25)).foregroundStyle(Cuadrao.ink)
    }
}

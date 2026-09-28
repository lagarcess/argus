import SwiftUI

/// Semantic values from the locked mobile palette, shared by every destination.
enum ArgusStyle {
    static let canvas = adaptive(light: 0xF9F9F9, dark: 0x151719)
    static let background = adaptive(light: 0xFFFFFF, dark: 0x191C1F)
    static let surface = adaptive(light: 0xF4F4F4, dark: 0x24282C)
    static let ink = adaptive(light: 0x191C1F, dark: 0xF4F4F5)
    static let secondary = adaptive(light: 0x505A63, dark: 0xB4BBC2)
    static let line = adaptive(light: 0xE7E7E9, dark: 0x303438)
    static let pageInset: CGFloat = 24
    static let sectionGap: CGFloat = 32
    static let controlHeight: CGFloat = 48

    static func body(_ size: CGFloat = 16, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("Inter-Regular", size: size, relativeTo: style)
    }

    static func display(_ size: CGFloat = 28, relativeTo style: Font.TextStyle = .title) -> Font {
        .custom("SpaceGrotesk-Medium", size: size, relativeTo: style)
    }

    private static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 0xff) / 255,
                           green: CGFloat((hex >> 8) & 0xff) / 255,
                           blue: CGFloat(hex & 0xff) / 255, alpha: 1)
        })
    }
}

/// The three filled polygons in the locked Argus angular A mark.
struct ArgusMark: Shape {
    func path(in rect: CGRect) -> Path {
        let polygons: [[CGPoint]] = [
            [(219,36),(253,36),(271,72),(282,95),(307,145),(318,168),(342,216),
             (350,232),(364,261),(379,291),(390,314),(431,396),(437,409),(437,411),
             (403,411),(395,395),(358,321),(347,298),(325,254),(314,231),(300,203),
             (291,184),(283,168),(262,126),(251,103),(236,73),(228,89),(217,111),
             (206,134),(187,172),(176,195),(156,236),(137,275),(128,294),(120,310),
             (90,370),(79,393),(70,411),(36,411),(37,406),(78,324),(89,301),
             (106,267),(117,244),(135,208),(146,185),(171,134),(182,112),
             (193,89),(205,65),(216,42)].map { CGPoint(x: $0.0, y: $0.1) },
            [(235,146),(239,151),(263,199),(273,218),(298,269),(309,292),(308,294),
             (197,295),(181,327),(170,350),(153,384),(142,407),(140,411),(106,411),
             (109,402),(178,264),(179,263),(261,263),(219,179),(220,174),(234,147)]
                .map { CGPoint(x: $0.0, y: $0.1) },
            [(292,326),(325,326),(335,345),(345,364),(356,387),(364,403),(367,409),
             (367,411),(333,411),(325,395),(293,331)].map { CGPoint(x: $0.0, y: $0.1) }
        ]
        var path = Path()
        let scale = min(rect.width / 473, rect.height / 447)
        let offset = CGPoint(x: rect.midX - 473 * scale / 2, y: rect.midY - 447 * scale / 2)
        for polygon in polygons {
            path.addLines(polygon.map { CGPoint(x: $0.x * scale + offset.x, y: $0.y * scale + offset.y) })
            path.closeSubpath()
        }
        return path
    }
}

struct PillButtonStyle: ButtonStyle {
    var primary = true
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(ArgusStyle.body())
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
            .frame(minHeight: ArgusStyle.controlHeight)
            .foregroundStyle(primary ? ArgusStyle.background : ArgusStyle.ink)
            .background(primary ? ArgusStyle.ink : ArgusStyle.surface, in: Capsule())
            .opacity(configuration.isPressed ? 0.75 : 1)
    }
}

struct IconButton: View {
    let title: LocalizedStringKey
    let symbol: String
    let identifier: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 20, weight: .regular))
                .frame(minWidth: 48, minHeight: 48)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityIdentifier(identifier)
    }
}

struct SampleNotice: View {
    var body: some View {
        Label("sample.notice", systemImage: "info.circle")
            .font(ArgusStyle.body(12, relativeTo: .caption))
            .foregroundStyle(ArgusStyle.secondary)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityIdentifier("sample.notice")
    }
}

struct SampleRow: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    let title: LocalizedStringKey
    let subtitle: LocalizedStringKey
    var symbol: String? = nil
    var trailing: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        Group {
            if let action {
                Button(action: action) { content }
                    .buttonStyle(.plain)
            } else {
                content
            }
        }
    }

    private var content: some View {
        HStack(alignment: .center, spacing: 14) {
            if let symbol {
                Image(systemName: symbol).frame(width: 24).accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 7) {
                Text(title).font(ArgusStyle.body())
                Text(subtitle).font(ArgusStyle.body(12, relativeTo: .caption))
                    .foregroundStyle(ArgusStyle.secondary)
                if dynamicTypeSize.isAccessibilitySize, let trailing {
                    Text(verbatim: trailing).font(ArgusStyle.body(13, relativeTo: .subheadline))
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            if !dynamicTypeSize.isAccessibilitySize, let trailing {
                Text(verbatim: trailing)
                    .font(ArgusStyle.body(13, relativeTo: .subheadline))
                    .multilineTextAlignment(.trailing)
            }
            if action != nil {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12)).foregroundStyle(ArgusStyle.secondary)
                    .accessibilityHidden(true)
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .padding(.vertical, 16)
        .frame(minHeight: 60)
        .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
        .contentShape(Rectangle())
    }
}

struct SamplePage<Content: View>: View {
    @ViewBuilder let content: () -> Content
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: ArgusStyle.sectionGap) {
                SampleNotice()
                content()
            }
            .padding(.horizontal, ArgusStyle.pageInset)
            .padding(.top, 20)
            .padding(.bottom, 24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollDismissesKeyboard(.interactively)
    }
}

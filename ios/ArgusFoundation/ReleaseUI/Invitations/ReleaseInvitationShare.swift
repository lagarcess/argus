import SwiftUI
import CoreImage.CIFilterBuiltins
import ArgusSession

struct ReleaseInvitationShare {
    let url: URL?
    var code: String? = nil
    var expiresAt: Date? = nil
    var testFlightURL: URL? = nil
}

struct ReleaseInvitationShareCard: View {
    let invitation: ReleaseInvitationShare
    let spanish: Bool
    var identifier = "release.invitation"

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let url = invitation.url {
                ReleaseInvitationQRCode(url: url, spanish: spanish)
                    .frame(maxWidth: .infinity)
                    .accessibilityIdentifier(identifier + ".qr")
            }
            if let code = invitation.code {
                VStack(alignment: .leading, spacing: 8) {
                    Text(spanish ? "Código de invitación" : "Invitation code")
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                    Text(code).font(.system(.title2, design: .monospaced))
                        .textSelection(.enabled)
                        .accessibilityIdentifier(identifier + ".code")
                }
            }
            if let url = invitation.url {
                Text(url.absoluteString).font(CuadraoTypography.caption)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier(identifier + ".link")
            }
            if let expiresAt = invitation.expiresAt {
                Text(spanish ? "Vence: \(expiresAt.formatted(date: .abbreviated, time: .shortened))"
                     : "Expires: \(expiresAt.formatted(date: .abbreviated, time: .shortened))")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            if let item = invitation.url?.absoluteString ?? invitation.code {
                ShareLink(item: item) {
                    Label(spanish ? "Compartir invitación" : "Share invitation", systemImage: "square.and.arrow.up")
                        .frame(maxWidth: .infinity, minHeight: 48).modifier(ReleaseProminentLabel())
                }
                .buttonStyle(.borderedProminent).tint(WelcomePalette.pine)
                .accessibilityIdentifier(identifier + ".share")
            }
            if let testFlightURL = invitation.testFlightURL {
                Link(destination: testFlightURL) {
                    Text(spanish ? "Instalar con TestFlight" : "Install with TestFlight").frame(minHeight: 44)
                }.accessibilityIdentifier(identifier + ".testFlight")
                Text(spanish ? "TestFlight instala la app; la invitación permite entrar."
                     : "TestFlight installs the app; the invitation provides access.")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
            }
            Text(spanish ? "Compartir el enlace no significa que la persona ya aceptó."
                 : "Sharing the link does not mean the person has accepted.")
                .font(CuadraoTypography.caption).foregroundStyle(.secondary)
        }
        .foregroundStyle(WelcomePalette.ink)
    }
}

struct ReleaseInvitationQRCode: View {
    private let image: UIImage?
    let spanish: Bool

    init(url: URL, spanish: Bool) {
        self.spanish = spanish
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(url.absoluteString.utf8)
        filter.correctionLevel = "M"
        if let code = filter.outputImage {
            // Core Image emits one pixel per module. Preserve four white modules
            // on every edge before scaling; decoration never enters this region.
            let extent = code.extent.insetBy(dx: -4, dy: -4)
            let white = CIImage(color: CIColor(red: 1, green: 1, blue: 1)).cropped(to: extent)
            let padded = code.composited(over: white).cropped(to: extent)
                .transformed(by: CGAffineTransform(scaleX: 8, y: 8))
            image = CIContext().createCGImage(padded, from: padded.extent).map { UIImage(cgImage: $0) }
        } else { image = nil }
    }

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).interpolation(.none).resizable().scaledToFit()
                    .frame(maxWidth: 240).background(.white)
                    .accessibilityLabel(spanish ? "QR de la misma invitación. También puedes compartir el enlace."
                                        : "QR for the same invitation. You can also share the link.")
            } else {
                Text(spanish ? "No se pudo mostrar el QR. Comparte el enlace."
                     : "The QR could not be displayed. Share the link.")
                    .font(CuadraoTypography.supporting)
            }
        }
    }
}

struct HouseholdInvitationShareView: View {
    let invitation: HouseholdInvitation
    let spanish: Bool

    var body: some View {
        if let url = invitation.link.flatMap(URL.init(string:)) ?? invitation.token.flatMap({ URL(string: "argus-household://invite#" + $0) }) {
            VStack(alignment: .leading, spacing: 16) {
                Text(spanish ? "Un lugar para lo compartido." : "A place for what you share.")
                    .font(CuadraoTypography.section)
                Text("household.consent").font(CuadraoTypography.supporting)
                Text(spanish ? "Esta invitación es para tu Hogar. No usa tus invitaciones personales."
                     : "This invitation is for your Household. It does not use your personal invitations.")
                    .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                ReleaseInvitationShareCard(invitation: ReleaseInvitationShare(url: url, code: invitation.code,
                                                                              expiresAt: InvitationDates.date(invitation.expiresAt)),
                                           spanish: spanish, identifier: "household.invite")
                Text("household.invitationPrepared").font(CuadraoTypography.caption)
            }.padding(.vertical, 8)
        } else {
            Text("household.linkUnavailable").font(.footnote).accessibilityIdentifier("household.invite.lost")
        }
    }
}

/// Prominent labels sit on the pine fill, so they take the on-accent ink instead of the page ink.
struct ReleaseProminentLabel: ViewModifier {
    @Environment(\.isEnabled) private var enabled
    func body(content: Content) -> some View {
        content.foregroundStyle(enabled ? WelcomePalette.onAccent : WelcomePalette.disabledInk)
    }
}

struct ReleaseInvitationPage<Content: View>: View {
    let title: String
    let subtitle: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                CuadraoBrand().frame(maxWidth: .infinity).accessibilityHidden(true)
                WelcomeSquares().frame(maxWidth: .infinity).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 12) {
                    Text(title).font(CuadraoTypography.screen)
                    Text(subtitle).font(CuadraoTypography.body).foregroundStyle(.secondary)
                }
                content()
            }
            .fixedSize(horizontal: false, vertical: true)
            .padding(24).frame(maxWidth: 560).frame(maxWidth: .infinity)
        }
        .background(WelcomePalette.background)
        .foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
        .scrollDismissesKeyboard(.interactively)
    }
}

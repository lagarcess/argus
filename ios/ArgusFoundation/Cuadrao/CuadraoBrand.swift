import SwiftUI

/// The Cuadrao lockup shared by welcome, sign-in and the invitation card. The mark is Marketing's approved
/// "Lean, calm" artwork (marketing/brand/cuadrao-mark-light.svg for light surfaces; the tiled icon on dark).
struct CuadraoBrand: View {
    var body: some View {
        HStack(spacing: 14) {
            Image("CuadraoMark")
                .resizable()
                .scaledToFit()
                .frame(width: 32, height: 32)
                .accessibilityHidden(true)

            Text("CUADRAO")
                .font(.system(.title3, weight: .medium))
                .tracking(4)
        }
    }
}

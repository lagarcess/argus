import SwiftUI

/// One provisional brand lockup shared by welcome and Home.
struct CuadraoBrand: View {
    var body: some View {
HStack(spacing: 14) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(WelcomePalette.pine)
                                .frame(width: 20, height: 20)
                                .offset(x: 6, y: -6)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(WelcomePalette.sage)
                                .frame(width: 20, height: 20)
                                .offset(x: -6, y: 6)
                            RoundedRectangle(cornerRadius: 1)
                                .fill(WelcomePalette.overlap)
                                .frame(width: 8, height: 8)
                        }
                        .frame(width: 32, height: 32)
                        .accessibilityHidden(true)

                        Text("CUADRAO")
                            .font(.system(.title3, weight: .medium))
                            .tracking(4)
                    }
    }
}

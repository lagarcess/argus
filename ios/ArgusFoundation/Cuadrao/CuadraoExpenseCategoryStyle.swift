import SwiftUI

/// Categories reuse Plan's accent family and Home's vector icon construction.
extension CanvasExpenseCategory {
    var color: Color {
        switch self {
        case .food: WelcomePalette.clay
        case .groceries: WelcomePalette.pine
        case .transport: WelcomePalette.sunshine
        case .home: WelcomePalette.bloom
        case .leisure: WelcomePalette.overlap
        case .other: WelcomePalette.ink.opacity(0.5)
        }
    }
    var imageName: String {
        switch self {
        case .home: "CuadraoAccount-property"
        case .transport: "CuadraoAccount-vehicle"
        case .other: "CuadraoAccount-asset"
        default: "CuadraoCategory-" + rawValue
        }
    }
}

struct CuadraoExpenseCategoryIcon: View {
    let category: CanvasExpenseCategory
    var body: some View {
        Image(category.imageName).resizable().scaledToFit().frame(width: 23, height: 23)
            .foregroundStyle(category.color)
            .frame(width: 42, height: 42)
            .background(category.color.opacity(0.09), in: RoundedRectangle(cornerRadius: 13))
            .accessibilityHidden(true)
    }
}

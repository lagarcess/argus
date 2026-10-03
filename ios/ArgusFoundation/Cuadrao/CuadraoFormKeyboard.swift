import SwiftUI

extension View {
    func cuadraoFormKeyboard() -> some View {
        submitLabel(.done)
            .onSubmit {
                UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            }
            .scrollDismissesKeyboard(.interactively)
    }
}

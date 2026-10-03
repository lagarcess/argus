import SwiftUI

struct CuadraoSpaceSelector: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let add: () -> Void
    var body: some View {
        HStack(spacing: 4) {
            ScrollViewReader { proxy in
                ScrollView(.horizontal) {
                    HStack(spacing: 24) {
                        ForEach(data.visibleSpaces) { space in
                            Button { data.selectedSpaceID = space.id } label: {
                                Text(space.title(spanish))
                                    .font(.subheadline.weight(data.selectedSpaceID == space.id ? .semibold : .regular))
                                    .foregroundStyle(data.selectedSpaceID == space.id ? Color.primary : Color.secondary)
                                    .frame(minHeight: 44).contentShape(Rectangle())
                            }.buttonStyle(.plain).id(space.id)
                                .accessibilityAddTraits(data.selectedSpaceID == space.id ? [.isSelected] : [])
                                .accessibilityIdentifier("cuadrao-space-" + space.id)
                        }
                    }
                }.scrollIndicators(.hidden)
                    .onChange(of: data.selectedSpaceID) { _, id in proxy.scrollTo(id) }
            }
            CuadraoSectionAddButton(title: spanish ? "Añadir o gestionar espacios" : "Add or manage spaces", action: add)
                .accessibilityLabel(spanish ? "Añadir o gestionar espacios" : "Add or manage spaces")
                .accessibilityIdentifier("cuadrao-spaces-add")
        }
    }
}

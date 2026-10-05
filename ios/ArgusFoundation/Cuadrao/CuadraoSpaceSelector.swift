import SwiftUI

struct CuadraoSpaceSelector: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    let add: () -> Void
    var body: some View {
        CuadraoSpaceSelectorLayout(selection: data.selectedSpaceID,
            addTitle: spanish ? "Añadir o gestionar espacios" : "Add or manage spaces",
            addIdentifier: "cuadrao-spaces-add", add: add) {
            ForEach(data.visibleSpaces) { space in
                Button { data.selectedSpaceID = space.id } label: {
                    CuadraoSpaceLabel(title: space.title(spanish), selected: data.selectedSpaceID == space.id)
                }.buttonStyle(.plain).id(space.id)
                    .accessibilityAddTraits(data.selectedSpaceID == space.id ? [.isSelected] : [])
                    .accessibilityIdentifier("cuadrao-space-" + space.id)
            }
        }
    }
}

struct CuadraoSpaceLabel: View {
    let title: String
    let selected: Bool
    var body: some View {
        Text(title)
            .font(.subheadline.weight(selected ? .semibold : .regular))
            .foregroundStyle(selected ? Color.primary : Color.secondary)
            .frame(minHeight: 44).contentShape(Rectangle())
    }
}

struct CuadraoSpaceSelectorLayout<Content: View>: View {
    let selection: String
    let addTitle: String
    let addIdentifier: String
    let add: () -> Void
    @ViewBuilder let content: () -> Content
    var body: some View {
        HStack(spacing: 4) {
            ScrollViewReader { proxy in
                ScrollView(.horizontal) {
                    HStack(spacing: 24, content: content)
                }.scrollIndicators(.hidden)
                    .onChange(of: selection) { _, id in proxy.scrollTo(id) }
            }
            CuadraoSectionAddButton(title: addTitle, action: add)
                .accessibilityLabel(addTitle)
                .accessibilityIdentifier(addIdentifier)
        }
    }
}

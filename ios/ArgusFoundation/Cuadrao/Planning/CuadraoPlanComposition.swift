import SwiftUI

struct CuadraoPlanPage<Header: View, Content: View, Footer: View>: View {
    let spanish: Bool
    var audience: Binding<Bool>? = nil
    var bottomSpace: CGFloat = 90
    @ViewBuilder let header: () -> Header
    @ViewBuilder let content: () -> Content
    @ViewBuilder let footer: () -> Footer

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header()
                if let audience { CuadraoPlanAudiencePicker(spanish: spanish, together: audience) }
                content()
                footer()
            }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, bottomSpace)
        }
        .scrollIndicators(.hidden)
        .background(WelcomePalette.background)
        .foregroundStyle(WelcomePalette.ink).tint(WelcomePalette.pine)
        .cuadraoSoftScrollEdges()
    }
}

struct CuadraoPlanForecastSection<Scope: View, Content: View, Explore: View>: View {
    let period: String
    @ViewBuilder let scope: () -> Scope
    @ViewBuilder let content: () -> Content
    @ViewBuilder let explore: () -> Explore

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            CuadraoPlanForecastHeading(period: period, scope: scope)
            content()
            explore()
        }
    }
}

struct CuadraoPlanExploreLink<Destination: View>: View {
    let spanish: Bool
    var example = false
    @ViewBuilder let destination: () -> Destination

    var body: some View {
        NavigationLink(destination: destination) {
            HStack {
                Text(example
                    ? (spanish ? "Explorar escenarios de ejemplo" : "Explore example scenarios")
                    : (spanish ? "Explorar escenarios" : "Explore scenarios"))
                Image(systemName: "chevron.right").font(.caption2).accessibilityHidden(true)
            }.font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                .frame(minHeight: 44).contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("plan-explore")
    }
}

struct CuadraoPlanColdStart<Action: View>: View {
    let spanish: Bool
    let detail: String
    @ViewBuilder let action: () -> Action

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            PlanLandscape(look: .sunshine).frame(height: 135)
            Text(spanish ? "Lo que viene empieza aquí." : "What's next starts here.")
                .font(CuadraoTypography.feature)
            Text(detail).font(.subheadline).foregroundStyle(.secondary)
            action().font(.subheadline.weight(.medium)).frame(minHeight: 44)
        }
    }
}

struct CuadraoPlanCollection<Rows: View, Archives: View>: View {
    let spanish: Bool
    let isEmpty: Bool
    var canCreate = true
    let create: () -> Void
    @ViewBuilder let rows: () -> Rows
    @ViewBuilder let archives: () -> Archives

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(spanish ? "Tus planes" : "Your plans").font(CuadraoTypography.section)
            rows()
            archives()
            if isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text(spanish ? "¿Qué tienes en mente?" : "What do you have in mind?")
                        .font(CuadraoTypography.section)
                    Text(spanish ? "Un viaje, un respiro, llegar a fin de mes con más espacio." : "A trip, a little breathing room, a month with more left over.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    PlanPrimaryButton(title: spanish ? "Crear mi primer plan" : "Make my first plan", symbol: "plus", action: create)
                        .disabled(!canCreate)
                }.padding(24).background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 26))
            }
        }
    }
}

struct CuadraoPlanArchiveLink<Destination: View>: View {
    let spanish: Bool
    @ViewBuilder let destination: () -> Destination

    var body: some View {
        NavigationLink(destination: destination) {
            Label(spanish ? "Archivados" : "Archived", systemImage: "archivebox")
                .font(CuadraoTypography.supporting).foregroundStyle(.secondary).frame(minHeight: 44)
        }.accessibilityIdentifier("plan-archives")
    }
}

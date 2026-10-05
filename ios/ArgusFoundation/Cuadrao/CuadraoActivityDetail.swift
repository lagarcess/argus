import SwiftUI

struct CuadraoActivityDetail: View {
    let data: CuadraoAccountsPreview
    let activityID: UUID
    let spanish: Bool
    let actions: (CanvasAccountSheet) -> Void
    let record: (UUID) -> Void
    @State private var chatFocus: CanvasChatFocus?

    var body: some View {
        Group {
            if let entry = data.activity.first(where: { $0.id == activityID }),
               let account = data.account(entry.accountID),
               !data.spaces.contains(where: { $0.id == account.spaceID && $0.deleted }) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        Text(entry.title).font(CuadraoTypography.feature)
                            .accessibilityIdentifier("activity-detail-title")
                        Text(account.currency + " " + (entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency))
                            .font(CuadraoTypography.amount).monospacedDigit()
                            .accessibilityIdentifier("activity-detail-amount")
                        LabeledContent(spanish ? "Tipo" : "Type", value: entry.income ? (spanish ? "Ingreso" : "Income") : (spanish ? "Gasto" : "Expense"))
                        if !entry.income {
                            LabeledContent(spanish ? "Categoría" : "Category") {
                                HStack {
                                    CuadraoExpenseCategoryIcon(category: entry.category)
                                    Text(entry.category.title(spanish))
                                }
                            }
                        }
                        LabeledContent(spanish ? "Fecha" : "Date") {
                            Text(entry.date, format: .dateTime.day().month(.wide).year())
                        }
                        NavigationLink {
                            CuadraoAccountCanvas(data: data, accountID: account.id, spanish: spanish, actions: actions, record: record)
                        } label: {
                            HStack(spacing: 16) {
                                CanvasAccountIcon(kind: account.kind)
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(account.displayName(spanish)).font(CuadraoTypography.action)
                                    Text(account.currency).font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary).accessibilityHidden(true)
                            }.frame(minHeight: 62).contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("activity-detail-account")
                        Button {
                            chatFocus = .activity(id: entry.id, title: entry.title)
                        } label: {
                            Label(spanish ? "Preguntar a Cuadrao" : "Ask Cuadrao", systemImage: "bubble")
                                .font(.subheadline).frame(minHeight: 44).contentShape(Rectangle())
                        }.buttonStyle(.plain).foregroundStyle(WelcomePalette.pine)
                            .accessibilityIdentifier("activity-detail-ask")
                    }.padding(24)
                }.background(WelcomePalette.background)
            } else {
                ContentUnavailableView(spanish ? "Movimiento no disponible" : "Activity unavailable", systemImage: "doc.text.magnifyingglass")
            }
        }.navigationTitle(spanish ? "Movimiento" : "Activity")
            .navigationBarTitleDisplayMode(.inline).toolbar(.visible, for: .navigationBar)
            .contextualCuadrao(focus: $chatFocus, spanish: spanish)
    }
}

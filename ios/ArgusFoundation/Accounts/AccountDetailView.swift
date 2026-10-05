import SwiftUI
import ArgusSession

struct AccountDetailView: View {
    let account: FinancialAccount
    @ObservedObject var model: AccountsModel
    @ObservedObject var loop: FinancialLoopModel
    var debtOrigin: FinancialDebtNavigation.Origin = .account
    var nativePlanNavigation = false
    var search: FinancialSearchModel? = nil
    @Environment(\.locale) private var locale

    private var current: FinancialAccount {
        model.accounts.first(where: { $0.id == account.id }) ?? account
    }
    private var spanish: Bool { locale.language.languageCode?.identifier == "es" }

    var body: some View {
        let account = current
        VStack(alignment: .leading, spacing: 30) {
            if account.isOptionalAsset {
                AssetDetailView(account: account, model: model, loop: loop)
            } else {
                CanvasAccountDetailContent(
                    value: ConnectedAccountPresentation.detail(account, spanish: spanish, locale: locale),
                    spanish: spanish, recordEnabled: loop.pendingConfirmation == nil,
                    checkEnabled: loop.pendingConfirmation == nil,
                    recordIdentifier: "accounts.record", checkIdentifier: "accounts.check",
                    record: { loop.record(current) }, check: { loop.check(current) }) {
                        AccountActivityView(loop: loop, account: account, debtOrigin: debtOrigin)
                    }
            }
            accountActions
            if !account.isOptionalAsset, let opening = account.opening {
                VStack(alignment: .leading, spacing: 16) {
                    Text("accounts.history").font(CuadraoTypography.section).accessibilityAddTraits(.isHeader)
                    ForEach(opening.revisions, id: \.revision) { revision in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(verbatim: account.currency + " " + AccountPresentation.amount(revision.amount, locale: locale))
                                .font(CuadraoTypography.rowAmount)
                            Text(verbatim: AccountPresentation.date(revision.asOf, zone: revision.timeZone, locale: locale))
                            Text(verbatim: revision.timeZone).font(.caption).foregroundStyle(.secondary)
                            if let reason = revision.reason { Text(verbatim: reason) }
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                            .accessibilityElement(children: .combine)
                    }
                }
            }
            AccountRequestStatus(model: model) { await model.refresh(account.id) }
        }
        .financialAccountDebtDestination(loop: loop, search: search, accountID: account.id, origin: debtOrigin, enabled: nativePlanNavigation)
        .foregroundStyle(WelcomePalette.ink)
        .toolbar {
            if #available(iOS 26.0, *) {
                ToolbarItem(placement: .topBarTrailing) { moreButton }.sharedBackgroundVisibility(.hidden)
            } else {
                ToolbarItem(placement: .topBarTrailing) { moreButton }
            }
        }
    }

    private var accountActions: some View {
        VStack(alignment: .leading, spacing: 0) {
            CanvasActionRow(title: NSLocalizedString("accounts.edit", comment: ""), symbol: "pencil") { model.edit(current) }
                .accessibilityIdentifier("accounts.edit")
            if !current.isOptionalAsset {
                CanvasActionRow(title: NSLocalizedString(current.opening == nil ? "accounts.opening.add" : "accounts.opening.correct", comment: ""),
                                symbol: "clock.arrow.circlepath") { model.opening(current) }
                    .accessibilityIdentifier("accounts.opening")
            }
            CanvasActionRow(title: NSLocalizedString(current.archived ? "accounts.restore" : "accounts.archive", comment: ""),
                            symbol: current.archived ? "arrow.uturn.backward" : "archivebox") {
                Task { await model.archive(current) }
            }.disabled(model.busy).accessibilityIdentifier("accounts.archive")
        }
    }

    private var moreButton: some View {
        Menu {
            Button("accounts.edit", systemImage: "pencil") { model.edit(current) }
            if !current.isOptionalAsset {
                Button("loop.record", systemImage: "plus") { loop.record(current) }.disabled(loop.pendingConfirmation != nil)
                Button("loop.check.title", systemImage: "checkmark.circle") { loop.check(current) }.disabled(loop.pendingConfirmation != nil)
                Button(current.opening == nil ? "accounts.opening.add" : "accounts.opening.correct", systemImage: "clock.arrow.circlepath") { model.opening(current) }
            }
            Button(current.archived ? "accounts.restore" : "accounts.archive", systemImage: current.archived ? "arrow.uturn.backward" : "archivebox") {
                Task { await model.archive(current) }
            }.disabled(model.busy)
        } label: {
            Image(systemName: "ellipsis").frame(width: 44, height: 44).contentShape(Rectangle())
        }.buttonStyle(.plain)
            .accessibilityLabel(spanish ? "Opciones de cuenta" : "Account actions")
            .accessibilityIdentifier("account-detail-options")
    }
}

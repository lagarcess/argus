import SwiftUI
import ArgusSession

struct AccountsDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    let showProfile: () -> Void
    let showSample: () -> Void

    var body: some View {
        if !auth.enabled {
            AccountsSampleView(showSample: showSample)
        } else if auth.state == .authenticated, let model = auth.accounts, let loop = auth.financialLoop {
            AccountsView(model: model, loop: loop)
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    PersonalContext()
                    Text("accounts.gate.title").font(ArgusStyle.display())
                    Text("accounts.gate.body").foregroundStyle(ArgusStyle.secondary)
                    Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                }.padding(24)
            }
        }
    }
}

struct AccountsView: View {
    @ObservedObject var model: AccountsModel
    @ObservedObject var loop: FinancialLoopModel
    @Environment(\.locale) private var locale
    @State private var managing = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                PersonalContext()
                if loop.pendingConfirmation != nil {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(LocalizedStringKey(loop.pendingTitle)).font(ArgusStyle.body(15))
                        Text("loop.pending.body").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                        Button("loop.pending.retry") { Task { await loop.retryPending() } }
                            .buttonStyle(PillButtonStyle()).disabled(loop.recovering)
                            .accessibilityIdentifier("loop.pending.retry.accounts")
                    }.padding(16).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
                }
                if let recoveryError = loop.recoveryErrorKey {
                    Text(LocalizedStringKey(recoveryError)).foregroundStyle(ArgusStyle.secondary)
                        .accessibilityIdentifier("loop.pending.error.accounts")
                }
                if let account = model.selected {
                    Button { model.back() } label: { Label("accounts.back", systemImage: "chevron.left") }
                        .frame(minHeight: 48).accessibilityIdentifier("accounts.back")
                    AccountDetailView(account: account, model: model, loop: loop)
                } else {
                    if managing {
                        Button { managing = false } label: { Label("accounts.back", systemImage: "chevron.left") }
                            .frame(minHeight: 48).accessibilityIdentifier("accounts.manage.back")
                        Text("accounts.manage").font(ArgusStyle.display())
                        Text("accounts.manage.body").foregroundStyle(ArgusStyle.secondary)
                        Text("accounts.active").font(ArgusStyle.display(23)).accessibilityAddTraits(.isHeader)
                        accountRows(archived: false)
                        Text("accounts.archived.section").font(ArgusStyle.display(23)).accessibilityAddTraits(.isHeader)
                        accountRows(archived: true)
                    } else {
                        Button("accounts.manage") { managing = true }
                            .frame(minHeight: 48).accessibilityIdentifier("accounts.manage")
                        if AccountPresentation.accounts(model.accounts, archived: false).isEmpty, !model.busy {
                            Text(model.accounts.isEmpty ? "accounts.empty.title" : "accounts.active.empty").font(ArgusStyle.display())
                            Text(model.accounts.isEmpty ? "accounts.empty.body" : "accounts.manage.body").foregroundStyle(ArgusStyle.secondary)
                        }
                        accountRows(archived: false)
                        Button("accounts.add") { model.create() }
                            .buttonStyle(PillButtonStyle()).accessibilityIdentifier("accounts.add")
                    }
                }
                if let error = model.errorKey, model.draft == nil {
                    Text(LocalizedStringKey(error)).accessibilityIdentifier("accounts.error")
                    Button("accounts.retry") { Task { await model.load() } }.frame(minHeight: 48)
                }
                if model.busy { ProgressView("accounts.loading") }

            }.padding(24)
        }
        .refreshable { await model.load(); if let account = model.selected { await loop.open(account) } }
        .task(id: model.identity?.revision) { await model.load() }
    }

    @ViewBuilder private func accountRows(archived: Bool) -> some View {
        let accounts = AccountPresentation.accounts(model.accounts, archived: archived)
        if managing, accounts.isEmpty, !model.busy {
            Text(archived ? "accounts.archived.empty" : "accounts.active.empty")
                .foregroundStyle(ArgusStyle.secondary)
        }
        VStack(spacing: 0) {
            ForEach(accounts, id: \.id) { account in
                Button { Task { await model.open(account); await loop.open(account) } } label: {
                    AccountRow(account: account)
                }.buttonStyle(.plain).accessibilityIdentifier("accounts.row.\(account.id)")
            }
        }
    }


}

struct AccountDetailView: View {
    let account: FinancialAccount
    @ObservedObject var model: AccountsModel
    @ObservedObject var loop: FinancialLoopModel
    @Environment(\.locale) private var locale
    var body: some View {
        AccountSummary(account: account, large: true)
        AccountActivityView(loop: loop, account: account)
        Button("accounts.edit") { model.edit(account) }.buttonStyle(PillButtonStyle(primary: false))
            .accessibilityIdentifier("accounts.edit")
        Button(account.opening == nil ? "accounts.opening.add" : "accounts.opening.correct") { model.opening(account) }
            .buttonStyle(PillButtonStyle()).accessibilityIdentifier("accounts.opening")
        if let opening = account.opening {
            Text("accounts.history").font(ArgusStyle.display(23)).accessibilityAddTraits(.isHeader)
            ForEach(opening.revisions, id: \.revision) { revision in
                VStack(alignment: .leading, spacing: 8) {
                    Text(verbatim: account.currency + " " + AccountPresentation.amount(revision.amount, locale: locale))
                        .monospacedDigit()
                    Text(verbatim: AccountPresentation.date(revision.asOf, zone: revision.timeZone, locale: locale))
                    Text(verbatim: revision.timeZone).font(ArgusStyle.body(12, relativeTo: .caption))
                    if let reason = revision.reason { Text(verbatim: reason) }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                    .accessibilityElement(children: .combine)
            }
        }
        Button(account.archived ? "accounts.restore" : "accounts.archive") { Task { await model.archive(account) } }
            .buttonStyle(PillButtonStyle(primary: false)).disabled(model.busy).accessibilityIdentifier("accounts.archive")
    }
}

struct AccountSummary: View {
    let account: FinancialAccount
    var large = false
    @Environment(\.locale) private var locale
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let nickname = account.nickname { Text(verbatim: nickname).font(large ? ArgusStyle.display() : ArgusStyle.body()) }
            Text(LocalizedStringKey("accounts.type." + account.type)).foregroundStyle(ArgusStyle.secondary)
            if account.balance.state == .known, let amount = account.balance.amount {
                Text(verbatim: account.currency + " " + AccountPresentation.amount(amount, locale: locale))
                    .font(large ? ArgusStyle.display(30) : ArgusStyle.body()).monospacedDigit()
            } else { Text("accounts.unknown") }
            if account.type == "credit_card", (account.balance.creditMinor ?? 0) > 0 {
                Text("accounts.creditBalance").font(ArgusStyle.body(12, relativeTo: .caption))
            } else if account.nature == "liability" {
                Text("accounts.signedBalance").font(ArgusStyle.body(12, relativeTo: .caption))
            }
            if account.archived { Text("accounts.archived").font(ArgusStyle.body(12, relativeTo: .caption)) }
        }.fixedSize(horizontal: false, vertical: true).accessibilityElement(children: .combine)
    }
}

/// Separator-only presentation preserves every digit without floating-point conversion.
enum AccountPresentation {
    static func accounts(_ records: [FinancialAccount], archived: Bool) -> [FinancialAccount] {
        records.filter { $0.archived == archived }
    }
    static func decimal(_ minor: Int64, digits: Int) -> String { decimal(String(minor), digits: digits) }
    static func decimal(_ minor: String, digits: Int) -> String {
        let negative = minor.hasPrefix("-")
        let magnitude = negative ? String(minor.dropFirst()) : minor
        let padded = String(repeating: "0", count: max(0, digits + 1 - magnitude.count)) + magnitude
        let point = padded.index(padded.endIndex, offsetBy: -digits)
        return (negative ? "-" : "") + (digits == 0 ? padded : String(padded[..<point]) + "." + String(padded[point...]))
    }
    static func symbol(_ type: String) -> String {
        switch type {
        case "cash": "banknote"
        case "checking": "building.columns"
        case "savings": "tray"
        case "investment": "chart.line.uptrend.xyaxis"
        case "credit_card": "creditcard"
        case "other_debt": "doc.text"
        case "property": "house"
        case "vehicle": "car"
        default: "square.stack"
        }
    }
    static func parseDate(_ exact: String) -> Date? {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = parser.date(from: exact) { return date }
        parser.formatOptions = [.withInternetDateTime]
        return parser.date(from: exact)
    }
    static func amount(_ exact: String, locale: Locale) -> String {
        let pieces = exact.split(separator: ".", omittingEmptySubsequences: false)
        var whole = String(pieces[0]); let negative = whole.hasPrefix("-")
        if negative { whole.removeFirst() }
        let groups = stride(from: whole.count, to: 0, by: -3).map { end -> String in
            let lower = whole.index(whole.startIndex, offsetBy: max(0, end - 3))
            let upper = whole.index(whole.startIndex, offsetBy: end)
            return String(whole[lower..<upper])
        }.reversed().joined(separator: locale.groupingSeparator ?? ",")
        return (negative ? "-" : "") + groups + (pieces.count > 1 ? (locale.decimalSeparator ?? ".") + pieces[1] : "")
    }
    static func date(_ exact: String, zone: String, locale: Locale) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fractional = parser.date(from: exact)
        parser.formatOptions = [.withInternetDateTime]
        guard let date = fractional ?? parser.date(from: exact), let timeZone = TimeZone(identifier: zone) else { return exact }
        let formatter = DateFormatter(); formatter.locale = locale; formatter.timeZone = timeZone
        formatter.dateStyle = .medium; formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

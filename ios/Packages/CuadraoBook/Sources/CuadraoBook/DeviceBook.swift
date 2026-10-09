import Foundation

/// The whole on-device book. One value, one JSON document: the store writes and reads exactly this.
public struct DeviceBook: Codable, Equatable, Sendable {
    /// The format this build reads and writes. A newer file opens read-only; an older one is migrated forward.
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    /// Bumped by every change. The store drops a save older than the newest it has written.
    public var revision: Int
    public var settings: BookSettings
    /// In display order; archived accounts keep their place.
    public var accounts: [BookAccount]

    public init(schemaVersion: Int = DeviceBook.currentSchemaVersion, revision: Int = 0, settings: BookSettings = BookSettings(),
                accounts: [BookAccount] = []) {
        self.schemaVersion = schemaVersion
        self.revision = revision
        self.settings = settings
        self.accounts = accounts
    }

    public static func empty() -> DeviceBook { DeviceBook() }

    private enum CodingKeys: String, CodingKey { case schemaVersion, revision, settings, accounts }

    /// Fields added later decode to their defaults, so a book written before they existed still opens.
    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try values.decode(Int.self, forKey: .schemaVersion)
        revision = try values.decodeIfPresent(Int.self, forKey: .revision) ?? 0
        settings = try values.decodeIfPresent(BookSettings.self, forKey: .settings) ?? BookSettings()
        accounts = try values.decodeIfPresent([BookAccount].self, forKey: .accounts) ?? []
    }
}

public struct BookSettings: Codable, Equatable, Sendable {
    /// The currency new accounts start in and Home totals lead with. Always a code in `CurrencyTable`.
    public var primaryCurrency: String?

    public init(primaryCurrency: String? = nil) {
        self.primaryCurrency = primaryCurrency
    }
}

public enum BookRuleError: Error, Equatable, Sendable {
    case currencyUnsupported
    case nicknameTooLong
    case amount(MoneyError)
    /// Debts and optional assets are typed as a positive amount.
    case negativeAmount
    case amountTooLarge
    case shareInvalid
    case accountLimit
    case accountNotFound
    /// The currency or the type is kept once the account has a recorded balance or movements.
    case currencyLocked
    case kindLocked
    /// The order given was not exactly the active accounts.
    case orderInvalid
}

extension DeviceBook {
    /// The preferred currency, or nil to clear it. A code the server would refuse is refused here too.
    public func settingPrimaryCurrency(_ code: String?) throws -> DeviceBook {
        var next = self
        if let code {
            guard let currency = CurrencyTable.currency(code) else { throw BookRuleError.currencyUnsupported }
            next.settings.primaryCurrency = currency.code
        } else {
            next.settings.primaryCurrency = nil
        }
        next.revision += 1
        return next
    }
}

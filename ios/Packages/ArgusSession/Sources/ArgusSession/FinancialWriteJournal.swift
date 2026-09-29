import Auth
import CryptoKit
import Foundation

/// The exact request a person confirmed. The body includes the reviewed versions
/// and preview token; a retry sends these same bytes with the same key.
public struct PendingFinancialConfirmation: Codable, Equatable, Sendable {
    public let ownerId: UUID
    public let originAccountId: UUID
    public let route: String
    public let path: String
    public let method: String
    public let body: Data
    public let key: UUID

    public init(ownerId: UUID, originAccountId: UUID, route: String, path: String,
                method: String, body: Data, key: UUID) {
        self.ownerId = ownerId
        self.originAccountId = originAccountId
        self.route = route
        self.path = path
        self.method = method
        self.body = body
        self.key = key
    }
}

public enum FinancialWriteJournalError: Error, Equatable, Sendable {
    case pendingConfirmation
    case invalidIdentity
    case storageUnavailable
}

/// One outstanding confirmed write per owner and API environment. It never
/// dispatches a request: recovery always requires an explicit user action.
public final class FinancialWriteJournal: @unchecked Sendable {
    private let lock = NSLock()
    private let storage: any AuthLocalStorage
    private let prefix: String

    public convenience init(configuration: SessionConfiguration) {
        self.init(storage: DeviceKeychain(service: configuration.keychainService), prefix: configuration.storagePrefix)
    }

    init(storage: any AuthLocalStorage, prefix: String) {
        self.storage = storage
        self.prefix = prefix
    }

    public func pending(for identity: SessionSnapshot) throws -> PendingFinancialConfirmation? {
        let owner = try Self.owner(identity)
        return try locked { try read(owner: owner) }
    }

    public func begin(_ write: PendingFinancialConfirmation, for identity: SessionSnapshot) throws {
        let owner = try Self.owner(identity)
        guard write.ownerId == owner, !write.body.isEmpty,
              write.method == "POST" || write.method == "PATCH",
              !write.route.isEmpty, (write.path.isEmpty || write.path.hasPrefix("/")), !write.path.hasPrefix("//")
        else { throw FinancialWriteJournalError.invalidIdentity }
        try locked {
            if let existing = try read(owner: owner) {
                guard existing == write else { throw FinancialWriteJournalError.pendingConfirmation }
                return
            }
            do { try storage.store(key: storageKey(owner: owner), value: JSONEncoder().encode(write)) }
            catch { throw FinancialWriteJournalError.storageUnavailable }
        }
    }

    public func clear(_ write: PendingFinancialConfirmation, for identity: SessionSnapshot) throws {
        let owner = try Self.owner(identity)
        guard write.ownerId == owner else { throw FinancialWriteJournalError.invalidIdentity }
        try locked {
            guard let existing = try read(owner: owner), existing == write else { return }
            do { try storage.remove(key: storageKey(owner: owner)) }
            catch { throw FinancialWriteJournalError.storageUnavailable }
        }
    }

    private static func owner(_ identity: SessionSnapshot) throws -> UUID {
        guard identity.phase == .authenticated,
              let id = identity.profile?.id,
              let owner = UUID(uuidString: id)
        else { throw FinancialWriteJournalError.invalidIdentity }
        return owner
    }

    private func read(owner: UUID) throws -> PendingFinancialConfirmation? {
        do {
            guard let data = try storage.retrieve(key: storageKey(owner: owner)) else { return nil }
            let write = try JSONDecoder().decode(PendingFinancialConfirmation.self, from: data)
            guard write.ownerId == owner else { throw FinancialWriteJournalError.storageUnavailable }
            return write
        } catch { throw FinancialWriteJournalError.storageUnavailable }
    }

    private func storageKey(owner: UUID) -> String {
        let digest = SHA256.hash(data: Data(owner.uuidString.utf8)).map { String(format: "%02x", $0) }.joined()
        return prefix + ".financial-confirmation." + digest
    }

    private func locked<T>(_ operation: () throws -> T) rethrows -> T {
        lock.lock(); defer { lock.unlock() }
        return try operation()
    }
}

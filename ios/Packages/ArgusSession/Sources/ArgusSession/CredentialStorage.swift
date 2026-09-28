import Auth
import Foundation
import Security

struct DeviceKeychain: AuthLocalStorage {
    let service: String
    private func query(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
         kSecAttrAccount as String: key, kSecAttrSynchronizable as String: false]
    }
    func store(key: String, value: Data) throws {
        let attributes: [String: Any] = [kSecValueData as String: value,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var status = SecItemUpdate(query(key) as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query(key).merging(attributes) { _, new in new } as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw SessionFailure.storageUnavailable }
    }
    func retrieve(key: String) throws -> Data? {
        var request = query(key)
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let value = result as? Data else { throw SessionFailure.storageUnavailable }
        return value
    }
    func remove(key: String) throws {
        let status = SecItemDelete(query(key) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw SessionFailure.storageUnavailable }
    }
}

/// Also journals tokens returned by Argus until SDK adoption has been durably verified.
struct PendingCredentials: Codable, Sendable {
    let accessToken: String
    let refreshToken: String
}

/// One lock binds generation validation to the actual storage operation. Checking only
/// before an async refresh would let a retired SDK overwrite the next account's tokens.
final class CredentialVault: @unchecked Sendable {
    private let lock = NSLock()
    private let backing: any AuthLocalStorage
    private let prefix: String
    private var generation: UInt64 = 0
    private var failed = false
    private var recovery: PendingCredentials?
    init(backing: any AuthLocalStorage, prefix: String) { self.backing = backing; self.prefix = prefix }

    func epoch() -> UInt64 { locked { generation } }
    @discardableResult func retire() -> UInt64 {
        locked { generation &+= 1; failed = false; return generation }
    }
    func check(_ epoch: UInt64) throws {
        try locked {
            guard epoch == generation else { throw SessionFailure.staleOperation }
            guard !failed else { throw SessionFailure.storageUnavailable }
        }
    }
    func session() throws -> Session? { try read("session") }
    func pending() throws -> PendingCredentials? {
        try locked {
            if let recovery { return recovery }
            do {
                guard let data = try backing.retrieve(key: prefix + ".pending") else { return nil }
                return try JSONDecoder().decode(PendingCredentials.self, from: data)
            } catch { throw SessionFailure.storageUnavailable }
        }
    }
    func savePending(_ value: PendingCredentials) throws {
        try locked {
            // If the device refuses the durable write, retain the issued credentials
            // in memory and block entry. Never pretend local deletion was sign-out.
            recovery = value
            do { try backing.store(key: prefix + ".pending", value: JSONEncoder().encode(value)) }
            catch { throw SessionFailure.storageUnavailable }
        }
    }
    func preflight() throws {
        try locked {
            do {
                try backing.store(key: prefix + ".availability", value: Data())
                try backing.remove(key: prefix + ".availability")
            } catch { throw SessionFailure.storageUnavailable }
        }
    }
    func removeSession() throws { try remove("session") }
    func removePending() throws {
        try locked {
            do { try backing.remove(key: prefix + ".pending"); recovery = nil }
            catch { throw SessionFailure.storageUnavailable }
        }
    }

    func sdkRead(key: String, epoch: UInt64) throws -> Data? {
        try scoped(epoch) { key == "argus.session" ? try backing.retrieve(key: prefix + ".session") : nil }
    }
    func sdkWrite(key: String, value: Data, epoch: UInt64) throws {
        try scoped(epoch) {
            guard key == "argus.session" else { throw SessionFailure.storageUnavailable }
            do { try backing.store(key: prefix + ".session", value: value) }
            catch {
                // A refresh can already have rotated the server token. Preserve the
                // returned credentials for revocation before reporting the failure.
                if let session = try? JSONDecoder().decode(Session.self, from: value) {
                    let pending = PendingCredentials(accessToken: session.accessToken, refreshToken: session.refreshToken)
                    recovery = pending
                    try? backing.store(key: prefix + ".pending", value: JSONEncoder().encode(pending))
                }
                throw SessionFailure.storageUnavailable
            }
        }
    }
    func sdkRemove(key: String, epoch: UInt64) throws {
        try scoped(epoch) {
            if key == "argus.session" { try backing.remove(key: prefix + ".session") }
        }
    }
    private func scoped<T>(_ epoch: UInt64, operation: () throws -> T) throws -> T {
        try locked {
            guard epoch == generation else { throw SessionFailure.staleOperation }
            do { return try operation() }
            catch { failed = true; throw SessionFailure.storageUnavailable }
        }
    }
    private func read<T: Decodable>(_ suffix: String) throws -> T? {
        try locked {
            do {
                guard let data = try backing.retrieve(key: prefix + "." + suffix) else { return nil }
                return try JSONDecoder().decode(T.self, from: data)
            } catch { throw SessionFailure.storageUnavailable }
        }
    }
    private func remove(_ suffix: String) throws {
        try locked {
            do { try backing.remove(key: prefix + "." + suffix) }
            catch { throw SessionFailure.storageUnavailable }
        }
    }
    private func locked<T>(_ operation: () throws -> T) rethrows -> T {
        lock.lock(); defer { lock.unlock() }; return try operation()
    }
}

struct EpochStorage: AuthLocalStorage {
    let vault: CredentialVault
    let epoch: UInt64
    func retrieve(key: String) throws -> Data? { try vault.sdkRead(key: key, epoch: epoch) }
    func store(key: String, value: Data) throws { try vault.sdkWrite(key: key, value: value, epoch: epoch) }
    func remove(key: String) throws { try vault.sdkRemove(key: key, epoch: epoch) }
}

/// SDK logout deletes its session before issuing the request. This isolated store
/// retains the durable pending record until the controller has actual revoke proof.
final class RevocationStorage: AuthLocalStorage, @unchecked Sendable {
    private let lock = NSLock()
    private let vault: CredentialVault
    private var data: Data?
    private var failed = false
    init(vault: CredentialVault) { self.vault = vault }
    func retrieve(key: String) throws -> Data? {
        lock.lock(); defer { lock.unlock() }
        return key == "argus.session" ? data : nil
    }
    func store(key: String, value: Data) throws {
        lock.lock(); defer { lock.unlock() }
        guard key == "argus.session" else { throw SessionFailure.storageUnavailable }
        do {
            let session = try JSONDecoder().decode(Session.self, from: value)
            try vault.savePending(.init(accessToken: session.accessToken, refreshToken: session.refreshToken))
            data = value
        } catch { failed = true; throw SessionFailure.storageUnavailable }
    }
    func remove(key: String) throws {
        lock.lock(); defer { lock.unlock() }
        if key == "argus.session" { data = nil }
    }
    func check() throws {
        lock.lock(); defer { lock.unlock() }
        if failed { throw SessionFailure.storageUnavailable }
    }
}

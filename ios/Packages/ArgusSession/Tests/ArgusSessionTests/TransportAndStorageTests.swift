import XCTest
@testable import ArgusSession

final class TransportAndStorageTests: XCTestCase, @unchecked Sendable {
    func testTransportConfigurationCannotStoreOrReplayCookies() {
        let configuration = SessionTransport.cookieFreeConfiguration()
        XCTAssertNil(configuration.httpCookieStorage)
        XCTAssertFalse(configuration.httpShouldSetCookies)
        XCTAssertEqual(configuration.httpCookieAcceptPolicy, .never)
        XCTAssertNil(configuration.urlCache)
    }

    func testTransportRejectsForeignRequestsAndRedirectResponses() async throws {
        let origin = URL(string: "https://api.example.test")!
        let foreign = URL(string: "https://foreign.example.test")!
        let transport = SessionTransport { _ in
            (Data(), HTTPURLResponse(url: foreign, statusCode: 200, httpVersion: nil, headerFields: nil)!)
        }
        do { _ = try await transport.send(URLRequest(url: foreign), origin: origin); XCTFail("Foreign request") }
        catch { XCTAssertEqual(error as? SessionFailure, .invalidConfiguration) }
        do { _ = try await transport.send(URLRequest(url: origin), origin: origin); XCTFail("Redirected response") }
        catch { XCTAssertEqual(error as? SessionFailure, .unavailable) }
    }

    func testRetiredStorageCannotReadWriteOrDeleteCurrentAccount() throws {
        let backing = MemoryStore()
        let vault = CredentialVault(backing: backing, prefix: "test")
        let old = EpochStorage(vault: vault, epoch: vault.epoch())
        vault.retire()
        let current = EpochStorage(vault: vault, epoch: vault.epoch())
        try current.store(key: "argus.session", value: Data("current".utf8))
        XCTAssertThrowsError(try old.retrieve(key: "argus.session"))
        XCTAssertThrowsError(try old.store(key: "argus.session", value: Data("old".utf8)))
        XCTAssertThrowsError(try old.remove(key: "argus.session"))
        XCTAssertEqual(try current.retrieve(key: "argus.session"), Data("current".utf8))
    }

    func testDifferentAPIOriginsCannotRestoreEachOthersCredentials() throws {
        let fixture = try SessionFixture()
        let other = try SessionConfiguration(argusAPIURL: URL(string: "https://another.example.test")!, supabaseURL: fixture.configuration.supabaseURL, publicAnonKey: fixture.configuration.publicAnonKey, keychainService: fixture.configuration.keychainService)
        let first = CredentialVault(backing: fixture.storage, prefix: fixture.configuration.storagePrefix)
        let second = CredentialVault(backing: fixture.storage, prefix: other.storagePrefix)
        try first.savePending(.init(accessToken: "synthetic", refreshToken: "synthetic"))
        XCTAssertNil(try second.pending())
    }
}

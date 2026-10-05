import Auth
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

    func testRetiredStorageCannotReadWriteOrDeleteCurrentAccount() async throws {
        let server = AuthServer()
        let sessionData = try await server.sessionData()
        let backing = MemoryStore()
        let vault = CredentialVault(backing: backing, prefix: "test")
        let old = EpochStorage(vault: vault, epoch: vault.epoch())
        vault.retire()
        let current = EpochStorage(vault: vault, epoch: vault.epoch())
        try current.store(key: "argus.session", value: sessionData)
        XCTAssertThrowsError(try old.retrieve(key: "argus.session"))
        XCTAssertThrowsError(try old.store(key: "argus.session", value: sessionData))
        XCTAssertThrowsError(try old.remove(key: "argus.session"))
        XCTAssertEqual(try JSONDecoder().decode(Session.self, from: XCTUnwrap(current.retrieve(key: "argus.session"))), try JSONDecoder().decode(Session.self, from: sessionData))
    }

    func testDifferentAPIOriginsCannotRestoreEachOthersCredentials() throws {
        let fixture = try SessionFixture()
        let other = try SessionConfiguration(argusAPIURL: URL(string: "https://another.example.test")!, supabaseURL: fixture.configuration.supabaseURL, publicAnonKey: fixture.configuration.publicAnonKey, keychainService: fixture.configuration.keychainService)
        let first = CredentialVault(backing: fixture.storage, prefix: fixture.configuration.storagePrefix)
        let second = CredentialVault(backing: fixture.storage, prefix: other.storagePrefix)
        try first.savePending(.init(accessToken: "synthetic", refreshToken: "synthetic"))
        XCTAssertNil(try second.pending())
    }
    func testSessionMethodPersistsWithRefreshAndLegacyUnknownStaysUnknown() async throws {
        let server = AuthServer()
        for method in [SessionSignInMethod.apple, .email, .google, nil] {
            let backing = MemoryStore()
            let owner = CredentialVault(backing: backing, prefix: "method")
            let initial = try await server.sessionData()
            if method == nil { try backing.store(key: "method.session", value: initial) }
            else { try owner.sdkWrite(key: "argus.session", value: initial, epoch: owner.epoch(), adoptingMethod: method) }
            let rotated = try await server.sessionData()
            try owner.sdkWrite(key: "argus.session", value: rotated, epoch: owner.epoch())
            XCTAssertEqual(try owner.signInMethod(), method)
            XCTAssertEqual(try owner.session()?.refreshToken, try JSONDecoder().decode(Session.self, from: rotated).refreshToken)
            try owner.removeSession()
            XCTAssertNil(try owner.signInMethod())
        }
    }

    func testUnsupportedOrMalformedEnvelopeNeverFallsBackToLegacy() async throws {
        let server = AuthServer()
        let raw = try await server.sessionData()
        for value in [2, "unknown"] as [Any] {
            var object = try XCTUnwrap(JSONSerialization.jsonObject(with: raw) as? [String: Any])
            object["version"] = value
            let backing = MemoryStore()
            try backing.store(key: "method.session", value: JSONSerialization.data(withJSONObject: object))
            let vault = CredentialVault(backing: backing, prefix: "method")
            XCTAssertThrowsError(try vault.session()) { XCTAssertEqual($0 as? SessionFailure, .storageUnavailable) }
        }
    }

    func testSDKCannotSwitchAccountsWithinOneEpoch() async throws {
        let server = AuthServer(), backing = MemoryStore()
        let vault = CredentialVault(backing: backing, prefix: "method")
        let initial = try await server.sessionData()
        try vault.sdkWrite(key: "argus.session", value: initial, epoch: vault.epoch(), adoptingMethod: .apple)
        var other = try XCTUnwrap(JSONSerialization.jsonObject(with: initial) as? [String: Any])
        var user = try XCTUnwrap(other["user"] as? [String: Any])
        user["id"] = UUID().uuidString; other["user"] = user
        XCTAssertThrowsError(try vault.sdkWrite(key: "argus.session", value: JSONSerialization.data(withJSONObject: other), epoch: vault.epoch()))
        XCTAssertEqual(try vault.session()?.user.id, try JSONDecoder().decode(Session.self, from: initial).user.id)
        XCTAssertThrowsError(try vault.check(vault.epoch()))
    }

}

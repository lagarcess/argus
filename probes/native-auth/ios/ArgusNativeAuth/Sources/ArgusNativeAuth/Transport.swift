import Foundation

/// Where the probe talks to. Values come from the test runner's environment.
public struct Stack: Sendable {
    public let argusAPI: URL
    public let supabaseURL: URL
    public let anonKey: String

    public init(argusAPI: URL, supabaseURL: URL, anonKey: String) {
        self.argusAPI = argusAPI
        self.supabaseURL = supabaseURL
        self.anonKey = anonKey
    }
}

public struct APIResponse: Sendable {
    public let status: Int
    public let body: [String: any Sendable]
    public let headers: [String: String]
    public let setCookies: [HTTPCookie]

    public var problemCode: String? {
        (body["code"] as? String) ?? ((body["detail"] as? [String: Any])?["code"] as? String)
    }
}

/// Bearer-only HTTP. The session never stores, sends, or accepts cookies, so
/// Argus's `sb-*` cookies cannot authenticate a request that forgot its bearer.
public final class BearerTransport: Sendable {
    let base: URL
    let session: URLSession
    let deviceIP: String?

    /// `deviceIP` stands in for Cloudflare's CF-Connecting-IP on a local stack,
    /// so each simulated install gets its own Argus rate-limit key.
    public init(base: URL, deviceIP: String? = nil) {
        self.base = base
        self.deviceIP = deviceIP
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.httpCookieAcceptPolicy = .never
        configuration.urlCache = nil
        session = URLSession(configuration: configuration)
    }

    public func send(
        _ method: String,
        _ path: String,
        bearer: String? = nil,
        json: [String: any Sendable]? = nil,
        headers: [String: String] = [:],
        onStarted: (@Sendable () -> Void)? = nil
    ) async throws -> APIResponse {
        let url = base.appending(path: "api/v1" + path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let deviceIP { request.setValue(deviceIP, forHTTPHeaderField: "CF-Connecting-IP") }
        if let bearer { request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization") }
        for (name, value) in headers { request.setValue(value, forHTTPHeaderField: name) }
        if let json { request.httpBody = try JSONSerialization.data(withJSONObject: json) }
        onStarted?()
        let (data, response) = try await session.data(for: request)
        let http = response as! HTTPURLResponse
        let fields = http.allHeaderFields as? [String: String] ?? [:]
        let body = (try? JSONSerialization.jsonObject(with: data)) as? [String: any Sendable] ?? [:]
        return APIResponse(
            status: http.statusCode,
            body: body,
            headers: Dictionary(uniqueKeysWithValues: fields.map { ($0.key.lowercased(), $0.value) }),
            setCookies: HTTPCookie.cookies(withResponseHeaderFields: fields, for: url)
        )
    }
}

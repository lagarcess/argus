/// Every account-scoped request records the epoch it started in. A response
/// that arrives after a sign-out or account switch is dropped, not rendered.
public actor AccountBoundary {
    public private(set) var epoch = 0
    private var cache: [String: [String: any Sendable]] = [:]

    public init() {}

    public func begin() -> Int { epoch }

    public func end() {
        epoch += 1
        cache.removeAll()
    }

    public func deliver(_ response: APIResponse, startedIn started: Int, cacheKey: String?) throws -> APIResponse {
        guard started == epoch else { throw ArgusAuthError.staleAccount }
        if let cacheKey { cache[cacheKey] = response.body }
        return response
    }

    public func cached(_ key: String) -> [String: any Sendable]? { cache[key] }
}

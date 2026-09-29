import Foundation

extension SessionController {
    public func openingPreview(accountId: UUID, request: WriteOpeningRequest, expectedIdentity: SessionSnapshot) async throws -> OpeningPreview {
        try await loopResponse(path: accountPath(accountId) + "/opening/preview", method: "POST", body: encoded(request), identity: expectedIdentity)
    }
    public func financialCategories(expectedIdentity: SessionSnapshot) async throws -> FinancialCategoryCatalog {
        try await loopResponse(route: "financial-categories", identity: expectedIdentity)
    }

    public func financialHome(expectedIdentity: SessionSnapshot) async throws -> FinancialHome {
        try await loopResponse(route: "financial-home", identity: expectedIdentity)
    }

    public func financialActivity(accountId: UUID, cursor: String? = nil, expectedIdentity: SessionSnapshot) async throws -> FinancialPage<FinancialActivity> {
        try await loopResponse(path: accountPath(accountId) + "/activity", query: pageQuery(cursor), identity: expectedIdentity)
    }

    public func financialActivityHistory(accountId: UUID, recordId: UUID, cursor: String? = nil, expectedIdentity: SessionSnapshot) async throws -> FinancialPage<FinancialActivity> {
        try await loopResponse(path: activityPath(accountId, recordId) + "/history", query: pageQuery(cursor), identity: expectedIdentity)
    }

    public func financialChecks(accountId: UUID, cursor: String? = nil, expectedIdentity: SessionSnapshot) async throws -> FinancialPage<FinancialCheck> {
        try await loopResponse(path: accountPath(accountId) + "/balance-checks", query: pageQuery(cursor), identity: expectedIdentity)
    }

    public func expensePreview(accountId: UUID, recordId: UUID? = nil, request: ExpenseRequest,
                               expectedIdentity: SessionSnapshot) async throws -> ExpensePreview {
        try await loopResponse(path: activityPath(accountId, recordId) + "/preview", method: "POST",
                               body: encoded(request), identity: expectedIdentity)
    }

    public func saveExpense(accountId: UUID, recordId: UUID? = nil, request: ExpenseRequest, key: UUID,
                            expectedIdentity: SessionSnapshot) async throws -> ExpenseReceipt {
        try await loopResponse(path: activityPath(accountId, recordId), method: recordId == nil ? "POST" : "PATCH",
                               body: encoded(request), key: key, identity: expectedIdentity)
    }

    public func balanceCheckPreview(accountId: UUID, request: BalanceCheckRequest,
                                    expectedIdentity: SessionSnapshot) async throws -> BalanceCheckPreview {
        try await loopResponse(path: accountPath(accountId) + "/balance-checks/preview", method: "POST",
                               body: encoded(request), identity: expectedIdentity)
    }

    public func saveBalanceCheck(accountId: UUID, request: BalanceCheckRequest, key: UUID,
                                 expectedIdentity: SessionSnapshot) async throws -> BalanceCheckReceipt {
        try await loopResponse(path: accountPath(accountId) + "/balance-checks", method: "POST",
                               body: encoded(request), key: key, identity: expectedIdentity)
    }

    private func accountPath(_ accountId: UUID) -> String { "/" + accountId.uuidString }
    private func activityPath(_ accountId: UUID, _ recordId: UUID?) -> String {
        accountPath(accountId) + "/activity" + (recordId.map { "/" + $0.uuidString } ?? "")
    }
    private func pageQuery(_ cursor: String?) -> [URLQueryItem] {
        cursor.map { [URLQueryItem(name: "cursor", value: $0)] } ?? []
    }
    private func loopResponse<Value: Decodable>(route: String = "financial-accounts", path: String = "",
                                               method: String = "GET", body: Data? = nil, key: UUID? = nil,
                                               query: [URLQueryItem] = [], identity: SessionSnapshot) async throws -> Value {
        let data = try await financialRequest(route: route, path: path, method: method, body: body,
                                              key: key?.uuidString, query: query, expectedIdentity: identity)
        do { return try JSONDecoder().decode(Value.self, from: data) }
        catch { throw SessionFailure.invalidResponse }
    }
}

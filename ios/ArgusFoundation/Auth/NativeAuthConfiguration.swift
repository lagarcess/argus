import Foundation
import ArgusSession

struct NativeAuthConfiguration {
    let session: SessionConfiguration
    let webURL: URL
    let captchaURL: URL

    static func load(bundle: Bundle = .main) throws -> Self? {
        let enabled = bundle.object(forInfoDictionaryKey: "ARGUS_AUTH_ENABLED")
        guard (enabled as? Bool == true) || (enabled as? String)?.lowercased() == "true" else { return nil }
        func value(_ key: String) throws -> String {
            guard let value = bundle.object(forInfoDictionaryKey: key) as? String,
                  !value.isEmpty, !value.contains("$(") else { throw SessionFailure.invalidConfiguration }
            return value
        }
        let api = try endpoint(value("ARGUS_API_URL"))
        let supabase = try endpoint(value("ARGUS_SUPABASE_URL"))
        let web = try endpoint(value("ARGUS_WEB_URL"))
        let captcha = try endpoint(value("ARGUS_CAPTCHA_URL"))
        guard web.path.isEmpty || web.path == "/", web.query == nil, captcha.query == nil else {
            throw SessionFailure.invalidConfiguration
        }
        return try Self(session: SessionConfiguration(
            argusAPIURL: api, supabaseURL: supabase,
            publicAnonKey: value("ARGUS_SUPABASE_ANON_KEY"),
            keychainService: (bundle.bundleIdentifier ?? "local.argus.foundation") + ".registered-session"
        ), webURL: web, captchaURL: captcha)
    }

    private static func endpoint(_ string: String) throws -> URL {
        guard let url = URL(string: string), let host = url.host,
              url.user == nil, url.password == nil, url.fragment == nil,
              url.scheme == "https" || (url.scheme == "http" && ["localhost", "127.0.0.1", "::1"].contains(host)) else {
            throw SessionFailure.invalidConfiguration
        }
        return url
    }

    var recoveryURL: URL { webURL.appendingPathComponent("auth/forgot-password") }
}

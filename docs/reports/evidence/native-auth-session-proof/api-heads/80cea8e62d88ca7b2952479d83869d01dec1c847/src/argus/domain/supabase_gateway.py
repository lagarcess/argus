# Committed extract of 80cea8e62d88ca7b2952479d83869d01dec1c847:src/argus/domain/supabase_gateway.py
# Kept so evidence_gate can resolve the #728 API head without fetching that commit.

134:def _supabase_client_options() -> ClientOptions:
144:def _auth_client_factory(url: str, key: str) -> AuthClientFactory:
185:    auth_client_factory: AuthClientFactory | None = None
211:            auth_client_factory=_auth_client_factory(url, auth_key),
222:        if self.auth_client_factory is None:
224:        return self.auth_client_factory()

def _auth_client_factory(url: str, key: str) -> AuthClientFactory:
    """One throwaway Auth client per call: the server keeps no user's session.

    A shared supabase-py client retains, auto-refreshes, and forwards as its
    default Authorization header the last session it signed in.
    """
    auth_url = f"{url.rstrip('/')}/auth/v1"
    headers = {"apiKey": key, "Authorization": f"Bearer {key}"}
    refuse_cookies = http.cookiejar.DefaultCookiePolicy(allowed_domains=[])
    http_client = httpx.Client(
        http2=False,
        timeout=120,
        cookies=http.cookiejar.CookieJar(policy=refuse_cookies),
    )

    def build() -> SyncGoTrueClient:
        return SyncGoTrueClient(
            url=auth_url,
            headers=dict(headers),
            auto_refresh_token=False,
            persist_session=False,
            flow_type="pkce",
            http_client=http_client,
        )

    return build


@dataclass
class SupabaseGateway(
    GuestAccountPersistenceMixin,
    ChatTurnLifecycleGatewayMixin,
    SupabaseConversationActivityMixin,
    SupabaseMessageReadMixin,
    SupabasePublicExcerptMixin,
    ConversationMessagePersistenceMixin,
    UsageCounterReader,
    DecisionAttachmentPersistenceMixin,
    SupabaseComputedAnswerReadMixin,
):

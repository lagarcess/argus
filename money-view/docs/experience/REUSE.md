# Argus presentation reuse

The local workspace adapts the actual Argus presentation while keeping its
production controllers outside the import closure. Local files live under
`money-view/web/src/argus`; the Vite entry keeps its local API and session owners.
No Next.js, Supabase client, `argus-api`, production flags or environment loader
is imported by these presentation components.

| Original source | Local owner | Retained / changed |
| --- | --- | --- |
| `web/components/chat/composer-model.ts` | `src/argus/composer-model.ts` | Segment serialization, normalized mention ranges, token replacement and deletion. Discovery records are an injected local `Mention` contract; asset-specific aliases are removed. |
| `web/components/chat/ChatInput.tsx` | `src/argus/composer-dom.ts`, `ArgusComposer.tsx` | Actual contenteditable DOM traversal, caret restoration, atomic tokens and send-acceptance behavior. JSX uses local scoped CSS and copy; discovery is injected, attachment action is explicit, composition events do not send. |
| `web/lib/responsive-layout.ts`, `web/components/layout/useResponsiveLayout.ts` | `src/argus/responsive-layout.ts`, `useResponsiveLayout.ts` | Shared external-store snapshots and 720/1024 width bands, copied with local imports. |
| `web/components/chat/ChatInterface.tsx`, `EmptyChatSurface.tsx`, `StarterActions.tsx` | `src/platform/PlatformApp.tsx` | Full conversation canvas, persistent composer, empty question surface, mobile starter strip. Local session and financial APIs replace the production controller. |
| `web/components/sidebar/ChatSidebar.tsx`, `SidebarShell.tsx` | `src/platform/PlatformApp.tsx`, `shell.css` | New chat/search/recents/profile hierarchy and narrow drawer. Existing financial routes are expandable destinations. |
| `web/app/fonts/*`, `web/public/icons/argus-192.png` | `public/fonts`, `public/icons` | Actual Argus Inter, Space Grotesk, font licenses and icon, served locally. Georgia remains the finance display face. |

The local native `Modal` remains the sole focus and scroll-lock owner for its
nested dialogs. Its `default`, `search` and `drawer` variants provide adaptive
geometry; no copied Argus keyboard/focus registry runs beside it. Search and chat
feature owners document their own component-level provenance.

## Integration contracts

`ArgusComposer` exports `locale`, `onSend(text, mentions?)`, `disabled?`,
`placeholder?`, `onAttach?`, `context?`, `onToast?`, `initialText?`, and optional
`discover(query, AbortSignal): Promise<Mention[]>`. A rejected or throwing send
preserves text; a successful acceptance clears it. `false` is the explicit
rejection signal. The caller owns all APIs and financial meaning.

`Mention` contains `id`, `type`, `label`, `insert_text`, optional description,
symbol, provider and serialized message range. Reference validation belongs to
the backend. No frontend label matching chooses a finance action.

The shell imports `ConversationPage(PlatformPageProps)` and
`RecentConversations({locale,revision,onNavigate})` from `features/chat`.
`#chat?conversation_id=...` opens a conversation; `#chat?draft=...` carries an
opaque draft identifier; `#chat?new=...` starts a new canvas. The chat-owned
`stageChatDraft` stores private text inside the user, household and canonical
data-generation scope. The shell and guest entry use that same owner. The chat
owner prevents replay on refresh or StrictMode. Legacy
`#saved?conversation_id=...` bridges to the corresponding full canvas.

`Omnisearch({locale,onClose,onNavigate,onAsk,revision})` owns search requests and
renders in `<Modal variant="search">`. Shell shortcuts only open it; typing does
not submit a question. Claim and guest entry use the backend session contract;
empty guests never acquire an invented currency. Display selections do not
convert balances or change account-owned action currencies.

Browser Back derives from the actual pure `web/lib/overlay-history.ts` owner and
`useOverlayBackDismiss.ts`, copied to `src/argus/overlay-history.ts` and
`useModalBackDismiss.ts`. The adaptation tracks native-dialog order for Back
only. It does not register keyboard handlers or trap focus. Hash navigation
consumes all temporary overlay entries before pushing the destination. This is
an intentional adaptation: the source replaced only the top entry and skipped
duplicate routes on Back, leaving invisible steps on Forward. The local owner
traverses to the underlying route once, then pushes the latest requested
destination, discarding temporary entries in both directions. Dismissal is
disabled during an atomic claim.

URL-owned settings panels use `Modal historyMode="route"`: their hash is the
history owner, so the dialog adds no second entry. Local-state dialogs use the
default overlay owner. `onNavigate(page, query, {replace: true})` supports explicit
route-panel dismissal without pushing another route. The router records an
app-owned parent hash; closing to that parent spends Back, while closing a
direct link replaces the current route. Native dialog remains the
only Escape, focus containment and scroll-lock owner in both modes.

## Presentation unit verification

From `money-view/web`, run:

```sh
node --test src/argus/composer-model.test.mjs src/argus/overlay-history.test.mjs
```

These 10 tests bundle the actual TypeScript owners in memory using the existing
esbuild dependency, then execute with Node's test runner. They preserve mention
ranges and atomic token behavior, canonical responsive boundaries, bidirectional
history at multiple overlay depths, and latest-destination ownership. Native
focus containment/restoration remains covered by real browser acceptance.

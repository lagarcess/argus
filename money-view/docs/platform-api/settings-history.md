# Settings conversation history

Settings composes the two existing household-visible history owners without merging their identities or changing their mutation permissions.

`GET /api/platform/settings/history?source=chat|assistant&state=active|archived|trashed&limit=20&offset=0` returns `{source,items,total,limit,offset}`. Source is required and closed to those two values. Limit is 1–100, offset is nonnegative; default state is archived. Each source delegates to its canonical list handler, retaining its order and household visibility. The settings UI shows Current conversations and Older conversations as separate sections with independent bounded pagination. Response source selects the existing PATCH restore and GET export endpoint; IDs are never inspected to infer their owner.

`POST /api/platform/settings/history/trash-all` accepts `{confirmation:"TRASH HOUSEHOLD CONVERSATIONS"}`. It requires a current household owner and atomically moves all active and archived conversations across both owners to trashed, including other household members' conversations. It uses the existing Store transaction, the existing older-history trash handler through a transaction-bound Store, and the chat owner's transaction-scoped trash helper. Any failure rolls back both. Response: `{trashed,counts:{chat,assistant},scope:"household",restorable:true}`. Repeating the operation returns zero for already-trashed records.

Restore and export retain their canonical permission checks and bounded export behavior. Older history access and exports remain available; no public share links or destructive permanent history deletion are added.

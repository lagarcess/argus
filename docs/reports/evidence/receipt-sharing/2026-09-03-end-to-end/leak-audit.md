# Leak audit, run against the private ids of the source records

Private ids harvested from the owner's transcript (GET /conversations/{id}/messages) and account:

- conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- user_id: 00000000-0000-0000-0000-000000000001
- agent_runtime_turn.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- agent_runtime_turn.request_id: bc4d259d-0f39-42e9-9c60-6d0c946ada74
- confirmation_card.actions.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- active_confirmation_reference.metadata.confirmation_card.actions.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- artifact_references.metadata.confirmation_card.actions.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- agent_runtime_turn.turn_id: 20e331f0-e8e1-46b7-abbd-571ace83a202
- chat_action.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- result_card.actions.payload.run_id: 61824352-a0b9-5577-a4e2-a3d902ab9f87
- result_card.actions.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- result_card.actions.payload.idea_id: 969635b0-70d8-4e3a-ae09-6fc20d1e8f61
- result_card.actions.payload.idea_version_id: 9ac12c2c-7494-4427-b8c3-34eec4021bda
- result_card.actions.payload.evidence_artifact_id: 5b5cfaeb-4272-46f6-891f-fe715987c36c
- result_card.idea_id: 969635b0-70d8-4e3a-ae09-6fc20d1e8f61
- result_card.idea_version_id: 9ac12c2c-7494-4427-b8c3-34eec4021bda
- result_card.evidence_artifact_id: 5b5cfaeb-4272-46f6-891f-fe715987c36c
- latest_run_id: 61824352-a0b9-5577-a4e2-a3d902ab9f87
- result_run_id: 61824352-a0b9-5577-a4e2-a3d902ab9f87
- result_conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- result_fact_bank.run_id: 61824352-a0b9-5577-a4e2-a3d902ab9f87
- result_fact_bank.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- result_fact_bank.result_card.actions.payload.run_id: 61824352-a0b9-5577-a4e2-a3d902ab9f87
- result_fact_bank.result_card.actions.payload.conversation_id: 08ca6511-f327-42d0-bb19-ce9d95b846df
- result_fact_bank.result_card.actions.payload.idea_id: 969635b0-70d8-4e3a-ae09-6fc20d1e8f61
- result_fact_bank.result_card.actions.payload.idea_version_id: 9ac12c2c-7494-4427-b8c3-34eec4021bda
- result_fact_bank.result_card.actions.payload.evidence_artifact_id: 5b5cfaeb-4272-46f6-891f-fe715987c36c
- result_fact_bank.result_card.idea_id: 969635b0-70d8-4e3a-ae09-6fc20d1e8f61
- result_fact_bank.result_card.idea_version_id: 9ac12c2c-7494-4427-b8c3-34eec4021bda
- result_fact_bank.result_card.evidence_artifact_id: 5b5cfaeb-4272-46f6-891f-fe715987c36c

Public artifacts searched: the public read JSON (public/receipts/{public_id}), the server-rendered /r/{public_id} HTML, the preview image headers.

Result: no private id appears in any public artifact. Marker words searched (openrouter, perplexity, alpaca, supabase, route_receipt, model, developer@argus.local, Mock Developer, langgraph, token, latency, cost_usd, conversation, run_id): the only hit is the string 'supabase' inside a Next.js chunk filename (node_modules_@supabase_postgrest-js) in the HTML, which is a bundler artifact of the app shell and carries no data.

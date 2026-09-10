# Selection-relevance diagnosis at frozen c6c28fef

Read-only investigation of two in-progress full-suite failures. No status was changed, no provider was called, and no source/Git edit was made. The completed scorecard was not available for this investigation.

## Spanish cybersecurity category

Case: `asset_discovery_category_spanish_issue_244`. Retained response lines 67-70 show a category request for cybersecurity, eight candidate suggestions with Spanish cybersecurity reasons, a Spanish framing sentence, and the judge verdict. The judge explicitly accepts that every delivered company matches the category, then fails only because `evidence_policy.data_class="movers"` and `max_age_seconds=300` are interpreted as the topic of retrieval. That inference is contradicted by the producer: `research_find.py:91` builds the same find-assets policy before the current-facts branch at line 93; `domain/research/cache.py:94-103` maps find-assets to the movers freshness class. It is not a selection relationship, requested category, or evidence that a movers search occurred. The retained task sequence uses `discovery_model_knowledge`, and the interpreter explicitly requested no current facts.

The evaluator copies the whole policy into every fact (`measurement_selection.py:171-177`) and passes those facts unchanged to the prose judge (`:364-373`). This is misleading semantic context, not evidence of an irrelevant answer. The pure-function probe proves the policy is movers/300 with question_kind=find_assets and current_survey=false, and that the judge projection preserves both the real candidate reason and this policy verbatim. This probe does not claim to recover the exact live judge input.

Smallest proposed follow-up: keep the full cache policy for deterministic source/currentness validation and raw evidence, but scope the judge view so cache class/retention cannot be mistaken for user intent. Preserve candidate reasons, source provenance/periods, the unchanged category expectations, and all structural failures. No per-tool or per-question acceptance exception is warranted.

## English Costco comparison

Case: `asset_discovery_comparison_anchor_english_issue_244`. Retained response lines 62-65 show the selected comparison-related call, candidates with retail-overlap reasons, and the actual sentence: "These verified candidates represent the closest competitors in Costco's retail category." The judge reports the delivered set WMT/TGT/AMZN/KR/DG and raises two distinct concerns: Dollar General weakens category relevance; and "verified" is unsupported because the grounding marker says general knowledge, not a current search.

The second rationale conflates independent facts. The model-knowledge composer still runs resolver/name and history validation (`discovery/composer.py:376-405`; `discovery/validation.py:140-157,187-243`). No sources means the candidate reason is unsourced/general knowledge (`measurement_outcome.py:125-130`); it does not mean identity was not verified. The judge view currently includes only identity/class/facts and does not clearly distinguish resolver verification from source grounding. That is an observation/rubric ambiguity.

The first rationale cannot be dismissed by repairing metadata: the retained answer strengthens broad retail-overlap suggestions to "closest competitors," and there is no retained ranking or independent category-relevance proof. The raw candidate response does contain a Dollar General reason, so a missing-reason observation bug is not established. Neither the original fixture nor the catalog requires a particular callable or relationship enum; the semantic comparison relevance remains a genuine judge-owned question. This diagnosis does not conclude that Costco would pass under a corrected evidence view.

## Evidence limits

`retained-response-contents.json` preserves only the 10 relevant response contents, with original JSONL line numbers and hashes. Provider reasoning/internal IDs are omitted. The source JSONL is append-in-progress, so provenance hashes each selected line rather than its changing whole file. The exact live judge request and final typed delivery were not retained in that JSONL; the judge notes report what it saw, and the current projection code establishes how those fields are supplied. Do not treat the controlled projection as a captured request. The eventual scorecard retains judged rendered context and selection evidence and can verify exact payload contents without another provider call.

`controlled-policy-projection.json` records six passing free assertions. `provenance.json` pins SHA c6c28fefe5b30c1f5d0a67656dc9c6fa025a44e2. No background processes remain.

"""Author rowless research outcomes; validate and present through the real declaration.

No callable invocation, provider retrieval, backtest, or public-receipt publication.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from argus.agent_runtime.research_tools import get_research_declarations
from argus.domain.tool_contracts import ToolCall, ToolOutcome

ROOT = Path('/Users/garces/.codex/worktrees/aa72/private-alpha-next')
OUT = Path('/private/tmp/registry-rowless-browser-c6c28fef')
HEAD = 'c6c28fefe5b30c1f5d0a67656dc9c6fa025a44e2'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == HEAD
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
declaration = next(item for item in get_research_declarations() if item.name == 'balanced_lookup')
authored = {
    'en': {
        'question': 'Explain this source context without numeric figures.',
        'narrative': 'This is an authored browser fixture for a completed research answer. The narrative and its source references remain available even when there are no numeric rows.',
        'source_titles': ['Authored source context', 'Authored supporting reference'],
    },
    'es-419': {
        'question': 'Explica el contexto de estas fuentes sin cifras numéricas.',
        'narrative': 'Este es un ejemplo escrito para verificar una respuesta de investigación completada en el navegador. La explicación y las referencias a sus fuentes siguen disponibles aunque no haya filas numéricas.',
        'source_titles': ['Contexto de la fuente del ejemplo', 'Referencia de apoyo del ejemplo'],
    },
}
fixtures = {}
for language, facts in authored.items():
    sources = [
        {'url': 'https://example.org/rowless-source-context', 'title': facts['source_titles'][0], 'source_date': '2026-09-09'},
        {'url': 'https://example.com/rowless-supporting-reference', 'title': facts['source_titles'][1], 'source_date': '2026-09-10'},
    ]
    typed_result = declaration.result_type.model_validate({
        'status': 'completed', 'answer': facts['narrative'], 'rows': [], 'sources': sources,
        'retrieved_at': '2026-09-10T05:00:00Z',
    })
    call = ToolCall(tool_name=declaration.name, call_id=f'rowless-{language}', arguments={
        'request': facts['question'], 'symbols': [], 'data_class': 'fundamentals',
    })
    card = declaration.result_card(call=call, outcome=ToolOutcome(
        status='succeeded', result=typed_result.model_dump(mode='json'),
    ), artifact_id=f'rowless-card-{language}')
    assert card.presentation.answer is None
    assert not card.presentation.rows
    assert card.presentation.narrative == facts['narrative']
    assert [source.url for source in card.presentation.sources] == [source['url'] for source in sources]
    fixtures[language] = {**facts, 'sources': sources, 'card': card.model_dump(mode='json')}
(OUT / 'fixture.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n')
paths = [
    'src/argus/agent_runtime/research_tools.py', 'src/argus/domain/tool_declaration.py',
    'src/argus/domain/tool_contracts.py', 'web/components/chat/ToolCardPresentation.tsx',
    'web/components/chat/ToolResultCard.tsx', 'web/components/chat/ChatMessage.tsx',
    'web/lib/tool-result-card.ts', 'web/e2e/support/mobile-shell-fixture.ts',
]
provenance = {
    'head': HEAD, 'repository_clean_at_generation': True,
    'acceptance_type': 'rendered authored fixture, not a provider answer or real API result',
    'declaration': declaration.name, 'callable': f'{declaration.handler.__module__}.{declaration.handler.__qualname__}',
    'typed_return': f'{declaration.result_type.__module__}.{declaration.result_type.__qualname__}',
    'card_binding': {'type': card.card_type, 'version': card.card_version},
    'presenter': 'argus.agent_runtime.research_tools.research_card_presentation',
    'invoked_handler': False, 'provider_calls': 0, 'backtests': 0,
    'fixture_sha256': hashlib.sha256((OUT / 'fixture.json').read_bytes()).hexdigest(),
    'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
    'served_source': 'git archive of the stated HEAD, web subtree, under checkout/web',
}
(OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
print(json.dumps({'head': HEAD, 'declaration': declaration.name, 'cases': list(fixtures), 'rows_per_case': 0, 'sources_per_case': 2, 'provider_calls': 0}))

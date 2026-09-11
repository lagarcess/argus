"""Inline Breakdown citations are bounded by this response's returned sources."""

from types import SimpleNamespace

import pytest
from argus.domain.research.contracts import ResearchSource
from argus.domain.result_readout_sources import accepted_breakdown_text
from markdown_it import MarkdownIt


@pytest.fixture(
    params=[
        ("en", "Quarterly results", "The company reported growth."),
        ("es-419", "Resultados trimestrales", "La empresa reportó crecimiento."),
    ]
)
def language_case(request):
    return request.param


def accept(text, language, sources):
    rendered, failure = accepted_breakdown_text(
        {"language": language, "text": text, "figures": []},
        facts={},
        language=language,
        sources=sources,
    )
    assert failure is None
    return rendered


def hrefs(text):
    return [
        child.attrGet("href")
        for block in MarkdownIt().parse(text)
        for child in block.children or []
        if child.type == "link_open"
    ]


def test_keep_descriptive_link_to_returned_source(language_case):
    language, title, sentence = language_case
    source = ResearchSource(url="https://example.com/results", title=title)
    text = f"{sentence} [{title}]({source.url})"
    assert accept(text, language, [source]) == text


@pytest.mark.parametrize("shape", ["{}", "<{}>", "[{0}]({0})"])
def test_bare_returned_url_uses_source_title(language_case, shape):
    language, title, sentence = language_case
    source = ResearchSource(url="https://example.com/results", title=title)
    rendered = accept(f"{sentence} {shape.format(source.url)}.", language, [source])
    assert rendered == f"{sentence} [{title}](<{source.url}>)."
    assert hrefs(rendered) == [source.url]


@pytest.mark.parametrize(
    "shape", ["[{label}]({url})", "[{label}][cite]\n\n[cite]: {url}"]
)
def test_unreturned_link_keeps_words_without_a_link(language_case, shape):
    language, title, sentence = language_case
    text = (
        sentence + " " + shape.format(label=title, url="https://invented.example/results")
    )
    rendered = accept(text, language, [])
    assert sentence + " " + title in rendered
    assert hrefs(rendered) == []


@pytest.mark.parametrize(
    "url",
    ["https://invented.example/results", "www.invented.example", "fake@invented.example"],
)
def test_unreturned_bare_url_cannot_be_autolinked_by_gfm(language_case, url):
    language, _, sentence = language_case
    rendered = accept(sentence + " " + url, language, [])
    assert f"`{url}`" in rendered
    assert hrefs(rendered) == []


def test_normal_markdown_destinations_and_source_titles_are_not_regex_delimited(
    language_case,
):
    language, title, _ = language_case
    source = ResearchSource(
        url="https://example.com/results_(2026)?a=1&b=2", title=title + " [2026]"
    )
    rendered = accept(
        f"[read]({source.url}) [invented](https://evil.example/a_(b))", language, [source]
    )
    assert hrefs(rendered) == [source.url]
    assert rendered.endswith("invented")
    assert hrefs(accept(source.url, language, [source])) == [source.url]


def test_code_and_unrelated_formatting_are_preserved(language_case):
    language, title, sentence = language_case
    source = ResearchSource(url="https://example.com/results", title=title)
    text = f"**{sentence}**\n\n`https://example.com/code`\n\n[{title}]({source.url})"
    assert accept(text, language, [source]) == text


def test_unreturned_destination_cannot_hide_behind_a_returned_url_label(language_case):
    language, title, _ = language_case
    source = ResearchSource(url="https://example.com/a_(b)", title=title)
    rendered = accept(f"[{source.url}](https://invented.example)", language, [source])
    assert rendered == f"`{source.url}`"
    assert hrefs(rendered) == []


def test_composer_checks_the_same_returned_sources_that_travel_to_the_panel(
    language_case,
):
    from argus.api.chat.breakdown import _llm_result_breakdown_with_metadata

    language, title, sentence = language_case
    source = ResearchSource(url="https://example.com/results", title=title)
    response = SimpleNamespace(
        draft={"language": language, "text": sentence + " " + source.url, "figures": []},
        sources=(source,),
        usage=None,
    )
    client = SimpleNamespace(run_structured=lambda *args, **kwargs: response)
    text, failure, _, sources = _llm_result_breakdown_with_metadata(
        {}, language=language, client=client
    )
    assert failure is None
    assert hrefs(text) == [source.url]
    assert title in text
    assert sources == (source,)

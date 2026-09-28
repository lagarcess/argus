"""Two synthetic markup changes, applied in memory to a page's HTML."""

import re


def rename_classes(html):
    return (
        html.replace('class="content-block spec-list"', 'class="block specs"')
        .replace('class="content-block feature-list"', 'class="block features"')
        .replace('<h1 class="content-block"', '<h1 class="block"')
    )


def restructure_specs(html):
    html = rename_classes(html)

    def spec(match):
        items = re.findall(
            r"<li><label>(.*?)</label><br>(.*?)</li>", match.group(1), re.S
        )
        rows = "".join(
            f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>'
            for k, v in items
        )
        return f'<section class="block specs">{rows}</section>'

    return re.sub(r'<ul class="block specs">(.*?)</ul>', spec, html, flags=re.S)


MUTATIONS = {"m1": rename_classes, "m2": restructure_specs}

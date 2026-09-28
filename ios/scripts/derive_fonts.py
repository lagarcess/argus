"""Derive bundled static fonts from the canonical web fonts (fonttools 4.65.0)."""
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from pathlib import Path
root = Path(__file__).resolve().parents[2]
for family, source, weight, style in [('Inter', 'InterVariable.woff2', 400, 'Regular'), ('Inter', 'InterVariable.woff2', 500, 'Medium'), ('SpaceGrotesk', 'SpaceGrotesk[wght].woff2', 500, 'Medium')]:
    font = TTFont(root / 'web/app/fonts' / source)
    axes = {a.axisTag: weight if a.axisTag == 'wght' else a.defaultValue for a in font['fvar'].axes}
    font = instantiateVariableFont(font, axes, inplace=False)
    font.flavor = None
    for record in font['name'].names:
        if record.nameID in (1, 2, 4, 6, 16, 17):
            value = {1: family, 2: style, 4: f'{family} {style}', 6: f'{family}-{style}', 16: family, 17: style}[record.nameID]
            record.string = value.encode(record.getEncoding())
    path = root / f'ios/ArgusFoundation/Resources/Fonts/{family}-{style}.ttf'
    font.save(path)
    print(path.name)

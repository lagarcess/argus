import re

JS_VAR = re.compile(r"\bvar\s+(ad\w+|promo\w+)\s*=\s*'?([^';\n]*?)'?\s*;")
SELLER_JS = ("adCustomerId", "adCustomerPromoGroup2")
VISITS = re.compile(r"visitado\s+(\d+)\s+veces")


def js_vars(script_texts):
    found = {}
    for text in script_texts:
        for name, value in JS_VAR.findall(text):
            if name not in SELLER_JS:
                found.setdefault(name, value.strip())
    return found


def squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def recovered(base, got):
    return [sum(1 for key, value in base.items() if got.get(key) == value), len(base)]

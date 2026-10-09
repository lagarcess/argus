"""Synthetic receipt photos and the stub's fixed reads, keyed by sha256."""

import hashlib
import json
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

TAG = sys.argv[1]
RECEIPTS = {
    "receipt-web.png": ["FERRETERIA LA ESQUINA SRL", "RNC 1-31-00000-0  (SYNTHETIC)", "Fecha: 2026-10-06", "",
                        "Pintura blanca 1 gal     1,850.00", "Brochas x3               1,073.73", "Subtotal                 2,923.73",
                        "ITBIS 18%                  526.27", "TOTAL RD$                3,450.00"],
    "receipt-noai.png": ["FARMACIA CAROL", "Av. 27 de Febrero (SYNTHETIC)", "Fecha: 2026-10-05", "",
                         "Acetaminofen x2            310.00", "Alcohol 70%                188.00", "TOTAL RD$                  498.00"],
    "receipt-whatsapp.png": ["COLMADO DON PEDRO", "Calle 4 #12 (SYNTHETIC)", "Fecha: 2026-10-07", "",
                             "Agua 5 gal x2              240.00", "Cafe 1 lb                  395.00", "ITBIS                       71.10",
                             "TOTAL RD$                  706.10"],
    "receipt-slow.png": ["LIBRERIA LA TRINITARIA", "Calle El Conde (SYNTHETIC)", "Fecha: 2026-10-07", "",
                         "Resma papel                 450.00", "TOTAL RD$                  450.00"],
}
font = ImageFont.load_default(size=22)
for name, lines in RECEIPTS.items():
    lines = [*lines, "", "SAMPLE DATA - NOT A REAL RECEIPT", f"run {TAG}"]
    image = Image.new("RGB", (520, 60 + 34 * len(lines)), "#fffdf7")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((24, 30 + index * 34), line, fill="#191c1f", font=font)
    image.save(name, format="PNG")


def read(merchant, day, items, tax, total, hold=0):
    purchase = {"page": 1, "row": 1, "evidence": "transaction", "status": "posted", "amount": total, "currency": "DOP",
                "occurred_on": day, "direction": "outflow", "kind_hint": "expense", "merchant": merchant}
    details = {"merchant": merchant, "occurred_on": day, "currency": "DOP",
               "items": [{"id": str(i + 1), "description": d, "total": t} for i, (d, t) in enumerate(items)], "tax": tax, "total": total}
    body = {"complete": True, "readable": True, "pages_read": [1], "observations": [purchase], "receipt": details}
    return {**body, "_hold_seconds": hold} if hold else body


digest = lambda name: hashlib.sha256(open(name, "rb").read()).hexdigest()
reads = {
    digest("receipt-web.png"): read("FERRETERIA LA ESQUINA SRL", "2026-10-06", [("Pintura blanca 1 gal", "1850.00"), ("Brochas x3", "1073.73")], "526.27", "3450.00"),
    digest("receipt-whatsapp.png"): read("COLMADO DON PEDRO", "2026-10-07", [("Agua 5 gal x2", "240.00"), ("Cafe 1 lb", "395.00")], "71.10", "706.10"),
    digest("receipt-slow.png"): read("LIBRERIA LA TRINITARIA", "2026-10-07", [("Resma papel", "450.00")], "0.00", "450.00", hold=120),
}
json.dump(reads, open("reads.json", "w"), indent=1)
shutil.copy("receipt-whatsapp.png", "media/700000000000901.png")
print({name: digest(name)[:12] for name in RECEIPTS})

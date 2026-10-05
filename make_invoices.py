"""Seeded generator of invented invoices for Lab 04 (instructor-side; students get the output).

One *base invoice* (number, date, BIN, items, quantities, prices) is rendered three times, in
Kazakh, Russian and English. The three variants carry the same numbers and differ only in the
text, so a per-language comparison is paired: any gap cannot come from harder digits.

Every invoice is stamped SAMPLE / "invented data". Company names, BINs and prices are made up.
The drawing code follows ``Lectures/lecture-06-multimodal/make_assets.py`` (``draw_invoice``,
``degrade``) but is standalone: that module imports Lab 01 code at import time.

Run (from the repo root, inside the project venv):

    .venv/bin/python Labs/lab-04-invoice-to-json/make_invoices.py

Output, under ``data/`` next to this file: ``clean/*.png``, ``degraded/*.jpg``, ``truth/*.json``
and ``manifest.json``. Same seed and same Pillow version give byte-identical files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import PIL
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "data"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

SEED = 2026
N_BASE = 8
LANGUAGES = ("kk", "ru", "en")
PAGE = (1100, 760)
INK = (22, 26, 24)
STAMP = (180, 83, 42)
GRID = (90, 100, 96)
COLS = [50, 100, 500, 620, 830, 1050]  # table column edges, as in the lecture invoice
TABLE_TOP, ROW_H = 290, 62
DATE_FIRST, DATE_SPAN_DAYS = date(2026, 9, 1), 31

# (kk, ru, en). Invented; any resemblance to a real company is accidental.
COMPANIES: list[dict[str, str]] = [
    {"kk": "«Алтын Дән» ЖШС", "ru": "ТОО «Алтын Дән»", "en": "Altyn Dan LLP"},
    {"kk": "«Нарынқол Трейд» ЖШС", "ru": "ТОО «Нарынкол Трейд»", "en": "Narynkol Trade LLP"},
    {"kk": "«Жетісу Астық» ЖШС", "ru": "ТОО «Жетысу Астык»", "en": "Zhetysu Astyk LLP"},
    {"kk": "«Сарыарқа Азық» ЖШС", "ru": "ТОО «Сарыарка Азык»", "en": "Saryarka Azyk LLP"},
    {"kk": "«Қазына Сауда» ЖШС", "ru": "ТОО «Казына Сауда»", "en": "Kazyna Sauda LLP"},
    {"kk": "«Арай Маркет» ЖШС", "ru": "ТОО «Арай Маркет»", "en": "Arai Market LLP"},
    {"kk": "«Таң Нұры» ЖШС", "ru": "ТОО «Тан Нуры»", "en": "Tan Nury LLP"},
    {"kk": "«Ерейментау Агро» ЖШС", "ru": "ТОО «Ерейментау Агро»", "en": "Ereymentau Agro LLP"},
    {"kk": "«Бөкейхан Фуд» ЖШС", "ru": "ТОО «Бокейхан Фуд»", "en": "Bokeikhan Food LLP"},
    {"kk": "«Шалқар Логистик» ЖШС", "ru": "ТОО «Шалкар Логистик»", "en": "Shalkar Logistic LLP"},
]

# Same index = same product in all three languages. ``price`` is a base unit price in tenge.
PRODUCTS: list[dict[str, Any]] = [
    {"kk": "Бидай ұны, 1-сорт, 50 кг", "ru": "Мука пшеничная, 1 сорт, 50 кг", "en": "Wheat flour, grade 1, 50 kg", "price": 14500},
    {"kk": "Күнбағыс майы, 5 л", "ru": "Масло подсолнечное, 5 л", "en": "Sunflower oil, 5 L", "price": 3200},
    {"kk": "Қант, 50 кг", "ru": "Сахар, 50 кг", "en": "Sugar, 50 kg", "price": 21800},
    {"kk": "Күріш, 25 кг", "ru": "Рис, 25 кг", "en": "Rice, 25 kg", "price": 16500},
    {"kk": "Қарақұмық, 25 кг", "ru": "Гречка, 25 кг", "en": "Buckwheat, 25 kg", "price": 19500},
    {"kk": "Картоп, 25 кг", "ru": "Картофель, 25 кг", "en": "Potatoes, 25 kg", "price": 6800},
    {"kk": "Сәбіз, 10 кг", "ru": "Морковь, 10 кг", "en": "Carrots, 10 kg", "price": 2400},
    {"kk": "Қызылша, 10 кг", "ru": "Свёкла, 10 кг", "en": "Beetroot, 10 kg", "price": 2100},
    {"kk": "Жұмыртқа, 30 дана", "ru": "Яйца, 30 шт", "en": "Eggs, 30 pcs", "price": 1900},
    {"kk": "Сүт, 1 л", "ru": "Молоко, 1 л", "en": "Milk, 1 L", "price": 450},
    {"kk": "Ірімшік, 1 кг", "ru": "Сыр, 1 кг", "en": "Cheese, 1 kg", "price": 3900},
    {"kk": "Шай, 100 г", "ru": "Чай, 100 г", "en": "Tea, 100 g", "price": 900},
    {"kk": "Тұз, 1 кг", "ru": "Соль, 1 кг", "en": "Salt, 1 kg", "price": 150},
    {"kk": "Сиыр еті, 1 кг", "ru": "Говядина, 1 кг", "en": "Beef, 1 kg", "price": 3800},
]

LABELS: dict[str, dict[str, Any]] = {
    "kk": {
        "title": "ЕСЕП-ФАКТУРА № {n}", "date": "Күні: {d}", "seller": "Сатушы: {v}", "bin": "БСН: {v}",
        "buyer": "Сатып алушы: {v}", "heads": ["№", "Атауы", "Саны", "Бағасы, теңге", "Сомасы, теңге"],
        "total": "Барлығы: {v} теңге", "seller_sign": "Сатушы қолы: ______________",
        "buyer_sign": "Сатып алушы қолы: ______________", "stamp": "ҮЛГІ · SAMPLE",
    },
    "ru": {
        "title": "СЧЁТ-ФАКТУРА № {n}", "date": "Дата: {d}", "seller": "Продавец: {v}", "bin": "БИН: {v}",
        "buyer": "Покупатель: {v}", "heads": ["№", "Наименование", "Кол-во", "Цена, тенге", "Сумма, тенге"],
        "total": "Итого: {v} тенге", "seller_sign": "Подпись продавца: ____________",
        "buyer_sign": "Подпись покупателя: ____________", "stamp": "ОБРАЗЕЦ · SAMPLE",
    },
    "en": {
        "title": "TAX INVOICE No. {n}", "date": "Date: {d}", "seller": "Seller: {v}", "bin": "BIN: {v}",
        "buyer": "Buyer: {v}", "heads": ["#", "Description", "Qty", "Unit price, KZT", "Amount, KZT"],
        "total": "Total: {v} KZT", "seller_sign": "Seller signature: ____________",
        "buyer_sign": "Buyer signature: ____________", "stamp": "SAMPLE",
    },
}


@dataclass(frozen=True)
class BaseInvoice:
    """Language-independent invoice content.

    Attributes:
        base_id: 1-based index of the base invoice.
        number: Four-digit invoice number, zero padded.
        day: Invoice date.
        seller: Index into ``COMPANIES``.
        buyer: Index into ``COMPANIES``, different from ``seller``.
        seller_bin: Invented 12-digit BIN of the seller.
        items: Tuples ``(product index, quantity, unit price in tenge)``.
    """

    base_id: int
    number: str
    day: date
    seller: int
    buyer: int
    seller_bin: str
    items: tuple[tuple[int, int, int], ...]


def make_base_invoices(n: int, seed: int) -> list[BaseInvoice]:
    """Draw ``n`` base invoices from a seeded RNG.

    Args:
        n: Number of base invoices.
        seed: Seed of the ``random.Random`` instance (no global RNG state is touched).

    Returns:
        The base invoices, in order of ``base_id``.
    """
    rng = random.Random(seed)
    out: list[BaseInvoice] = []
    for base_id in range(1, n + 1):
        seller, buyer = rng.sample(range(len(COMPANIES)), 2)
        products = rng.sample(range(len(PRODUCTS)), rng.randint(2, 4))
        items = []
        for p in products:
            base_price = PRODUCTS[p]["price"]
            step = 10 if base_price < 1000 else 50
            items.append((p, 5 * rng.randint(1, 30), round(base_price * rng.uniform(0.9, 1.1) / step) * step))
        out.append(BaseInvoice(
            base_id=base_id,
            number=f"{rng.randint(1, 9999):04d}",
            day=DATE_FIRST + timedelta(days=rng.randint(0, DATE_SPAN_DAYS)),
            seller=seller,
            buyer=buyer,
            seller_bin=str(rng.randint(10**11, 10**12 - 1)),
            items=tuple(items),
        ))
    return out


def build_truth(base: BaseInvoice, lang: str) -> dict[str, Any]:
    """Ground truth for one language variant; the schema matches the Lecture 5.1 invoice.

    Args:
        base: Language-independent content.
        lang: One of ``LANGUAGES``.

    Returns:
        Dict with ``invoice_number``, ``date`` (ISO), ``seller_name``, ``seller_bin``,
        ``buyer_name``, ``items`` and ``total``.
    """
    items = [{"name": PRODUCTS[p][lang], "qty": q, "unit_price": u, "amount": q * u} for p, q, u in base.items]
    return {
        "invoice_number": base.number,
        "date": base.day.isoformat(),
        "seller_name": COMPANIES[base.seller][lang],
        "seller_bin": base.seller_bin,
        "buyer_name": COMPANIES[base.buyer][lang],
        "items": items,
        "total": sum(i["amount"] for i in items),
    }


def count_fields(truth: dict[str, Any]) -> int:
    """Scalar fields a grader compares: 5 header fields, 4 per item row (name, qty, price, amount), the total."""
    return 5 + 4 * len(truth["items"]) + 1


def money(n: int) -> str:
    """Group digits with a no-break space: 1509000 -> '1 509 000'."""
    return f"{n:,}".replace(",", "\xa0")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the project font (Arial Unicode covers Kazakh, Russian and Latin)."""
    return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_PATH, size)


def missing_glyphs(text: str, fnt: ImageFont.FreeTypeFont) -> set[str]:
    """Characters of ``text`` that the font draws as its .notdef box (compared with U+0378)."""
    notdef = bytes(fnt.getmask("͸"))
    return {ch for ch in set(text) if not ch.isspace() and bytes(fnt.getmask(ch)) == notdef}


class Canvas:
    """A PIL image with a text helper that refuses to draw characters the font lacks."""

    def __init__(self) -> None:
        self.img = Image.new("RGB", PAGE, (252, 252, 250))
        self.draw = ImageDraw.Draw(self.img)

    def text(self, xy: tuple[float, float], txt: str, size: int, *, bold: bool = False,
             fill: tuple[int, int, int] = INK, right_edge: float | None = None,
             max_width: float | None = None) -> None:
        """Draw ``txt``; right-align to ``right_edge`` when given.

        Raises:
            RuntimeError: If a glyph is missing, or the text is wider than ``max_width``.
        """
        fnt = font(size, bold)
        missing = missing_glyphs(txt, fnt)
        if missing:
            raise RuntimeError(f"font has no glyph for {sorted(missing)} in {txt!r}")
        width = self.draw.textlength(txt, font=fnt)
        if max_width is not None and width > max_width:
            raise RuntimeError(f"{txt!r} is {width:.0f}px wide, limit {max_width:.0f}px")
        x = xy[0] if right_edge is None else right_edge - width
        self.draw.text((x, xy[1]), txt, font=fnt, fill=fill)


def draw_invoice(truth: dict[str, Any], day_text: str, lang: str) -> Image.Image:
    """Render one invoice as a plain table, in the layout of the lecture invoice.

    Args:
        truth: Ground truth of the invoice (the picture shows exactly these values).
        day_text: Date as printed, ``DD.MM.YYYY``.
        lang: One of ``LANGUAGES``.

    Returns:
        The clean RGB image, ``PAGE`` pixels.
    """
    lab = LABELS[lang]
    c = Canvas()
    c.text((50, 36), lab["title"].format(n=truth["invoice_number"]), 34, bold=True, max_width=700)
    c.text((50, 84), lab["date"].format(d=day_text), 24)
    c.draw.rectangle((790, 30, 1050, 100), outline=STAMP, width=3)
    c.text((810, 40), lab["stamp"], 22, bold=True, fill=STAMP, max_width=230)
    c.text((810, 72), "invented data", 18, fill=STAMP)
    c.text((50, 140), lab["seller"].format(v=truth["seller_name"]), 24, max_width=700)
    c.text((50, 176), lab["bin"].format(v=truth["seller_bin"]), 24)
    c.text((50, 220), lab["buyer"].format(v=truth["buyer_name"]), 24, max_width=980)
    rows = [[str(i + 1), it["name"], str(it["qty"]), money(it["unit_price"]), money(it["amount"])]
            for i, it in enumerate(truth["items"])]
    n_rows = len(rows) + 1
    c.draw.rectangle((COLS[0], TABLE_TOP, COLS[-1], TABLE_TOP + ROW_H), fill=(226, 236, 234))
    for r, cells in enumerate([lab["heads"]] + rows):
        y = TABLE_TOP + r * ROW_H + 18
        for col, txt in enumerate(cells):
            cell_w = COLS[col + 1] - COLS[col] - 24
            if col >= 2:
                c.text((0, y), txt, 22, bold=r == 0, right_edge=COLS[col + 1] - 12, max_width=cell_w)
            else:
                c.text((COLS[col] + 12, y), txt, 22, bold=r == 0, max_width=cell_w)
    bottom = TABLE_TOP + n_rows * ROW_H
    for r in range(n_rows + 1):
        c.draw.line((COLS[0], TABLE_TOP + r * ROW_H, COLS[-1], TABLE_TOP + r * ROW_H), fill=GRID, width=2)
    for x in COLS:
        c.draw.line((x, TABLE_TOP, x, bottom), fill=GRID, width=2)
    c.text((0, bottom + 24), lab["total"].format(v=money(truth["total"])), 28, bold=True, right_edge=COLS[-1])
    c.text((50, PAGE[1] - 90), lab["seller_sign"], 22)
    c.text((620, PAGE[1] - 90), lab["buyer_sign"], 22)
    return c.img


def degrade(img: Image.Image) -> Image.Image:
    """A bad phone photo or fax: 40 % of the resolution, 2 degrees of rotation, slight blur."""
    small = img.resize((round(img.width * 0.4), round(img.height * 0.4)), Image.LANCZOS)
    rotated = small.rotate(2.0, resample=Image.BICUBIC, expand=True, fillcolor=(235, 235, 232))
    return rotated.filter(ImageFilter.GaussianBlur(0.8))


def sha256(path: Path) -> str:
    """Hex SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(out: Path, n_base: int, seed: int) -> dict[str, Any]:
    """Write all images and truth files under ``out`` and return the manifest.

    Args:
        out: Output directory (created if missing).
        n_base: Number of base invoices; the document count is ``n_base * len(LANGUAGES)``.
        seed: RNG seed.

    Returns:
        The manifest dict that is also written to ``out/manifest.json``.
    """
    for sub in ("clean", "degraded", "truth"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    docs: list[dict[str, Any]] = []
    for base in make_base_invoices(n_base, seed):
        for lang in LANGUAGES:
            doc_id = f"inv{base.base_id:02d}_{lang}"
            truth = build_truth(base, lang)
            clean = draw_invoice(truth, base.day.strftime("%d.%m.%Y"), lang)
            clean_path, bad_path, truth_path = (
                out / "clean" / f"{doc_id}.png", out / "degraded" / f"{doc_id}.jpg", out / "truth" / f"{doc_id}.json")
            clean.save(clean_path)
            degrade(clean).save(bad_path, quality=25)
            truth_path.write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            docs.append({
                "id": doc_id, "base_id": base.base_id, "lang": lang,
                "n_fields": count_fields(truth),
                "sha256": {"clean": sha256(clean_path), "degraded": sha256(bad_path), "truth": sha256(truth_path)},
            })
    manifest = {"seed": seed, "n_base": n_base, "languages": list(LANGUAGES), "pillow": PIL.__version__,
                "n_docs": len(docs), "docs": docs}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--n-base", type=int, default=N_BASE)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    manifest = generate(args.out, args.n_base, args.seed)
    n_fields = sum(d["n_fields"] for d in manifest["docs"])
    print(f"{manifest['n_docs']} documents, {n_fields} fields in total -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

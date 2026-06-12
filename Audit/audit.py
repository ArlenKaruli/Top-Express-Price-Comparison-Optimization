import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation


LEI_600_PRODUCTS = {
    3: "Total Ero Exp Caffe Moneta",
    4: "Total Ero Exp Caffe Lungo Moneta",
    5: "Total Ero Exp Macchiato Moneta",
    6: "Total Ero Exp Cappuccino Moneta",
    7: "Total Ero Irish Caffe Moneta",
    8: "Total Ero Irish Caffe Lungo Moneta",
    9: "Total Ero Irish Macchiato Moneta",
    10: "Total Ero Irish Cappuccino Moneta",
    11: "Total Ero Ginseng Caffe Moneta",
    12: "Total Ero Ginseng Caffe Lungo Moneta",
    13: "Total Ero Ginseng Macchiato Moneta",
    14: "Total Ero Ginseng Cappuccino Moneta",
    15: "Total Ero Exp Mocaccino Moneta",
    16: "Total Ero Irish Mochaccino Moneta",
    17: "Total Ero Ginseng Mochaccino Moneta",
    18: "Total Ero Latte Moneta",
    19: "Total Ero Latte Cacao Moneta",
    20: "Total Ero Cioccolato Moneta",
    21: "Total Ero Cioccolato Forte Moneta",
    22: "Total Ero Cioccolata Al Latte Moneta",
    23: "Total Ero Exp Latte Macchiato Moneta",
    24: "Total Ero Irish Latte Macchiato Moneta",
    25: "Total Ero Ginseng Latte Macchiato Moneta",
    26: "Total Ero Te Al Limone Moneta",
}

LEI_600_STANDARD_PRODUCTS = {
    3: "Total Ero Ginseng Caffe Moneta",
    4: "Total Ero Irish Caffe Moneta",
    5: "Total Ero Exp Caffe Moneta",
    6: "Total Ero Exp Caffe Lungo Moneta",
    7: "Total Ero Exp Macchiato Moneta",
    8: "Total Ero Exp Cappuccino Moneta",
    9: "Total Ero Latte Macchiato Moneta",
    10: "Total Ero Cioccolata Al Latte Moneta",
    11: "Total Ero Latte Moneta",
    12: "Total Ero Cioccolato Moneta",
    13: "Total Ero Te Al Limone Moneta",
}

LEI_400_PRODUCTS = {
    3: (
        "Total Ero Ginseng Caffe Moneta",
        "Total Ero Ginseng Caffe Lungo Moneta",
    ),
    4: "Total Ero Exp Caffe Moneta",
    5: "Total Ero Exp Caffe Lungo Moneta",
    6: "Total Ero Exp Macchiato Moneta",
    7: "Total Ero Exp Cappuccino Moneta",
    8: "Total Ero Exp Mocaccino Moneta",
    9: "Total Ero Latte Caffe Moneta",
    10: "Total Ero Latte Moneta",
    11: "Total Ero Cioccolata Al Latte Moneta",
    12: "Total Ero Cioccolato Moneta",
    13: "Total Ero Te Al Limone Moneta",
}

LEI_300_PRODUCTS = {
    code: product
    for code, product in LEI_600_PRODUCTS.items()
    if code <= 18
}
LEI_300_PRODUCTS.update(
    {
        19: "Total Ero Cioccolata Al Latte Moneta",
        20: "Total Ero Cioccolato Moneta",
        21: "Total Ero Cioccolato Forte Moneta",
        22: "Ero Te Al Limone",
    }
)

MACHINES = {
    "1": ("LEI 600", LEI_600_PRODUCTS),
    "2": ("LEI 600 Standarte", LEI_600_STANDARD_PRODUCTS),
    "3": ("LEI 400", LEI_400_PRODUCTS),
    "4": ("LEI 400+", LEI_600_PRODUCTS),
    "5": ("LEI 300", LEI_300_PRODUCTS),
}

MACHINE_LABEL = re.compile(
    r"\blei\s*(?:600\s*(?:standart(?:e)?)?|400\s*\+?|300)\b",
    re.IGNORECASE,
)


def normalize_product_name(value):
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = MACHINE_LABEL.sub(" ", text.strip())
    text = re.sub(r"[^\w]+", " ", text.casefold())
    text = re.sub(r"\s+", " ", text).strip()

    # Some Windows terminals paste "Caffè" as "Caff?" and leave "caff".
    text = re.sub(r"\bcaff\b", "caffe", text)
    # "Chiave" entries use the same representative code as "Moneta".
    text = re.sub(r"\bchiave$", "moneta", text)
    # Treat common spelling variants from the Excel exports as equivalent.
    text = re.sub(r"\bmachiato\b", "macchiato", text)
    text = re.sub(r"\bmoc+h?accino\b", "mocaccino", text)
    text = re.sub(r"\bmochaccino\b", "mocaccino", text)
    text = re.sub(r"\bcioccolata\b", "cioccolato", text)
    return text


def product_aliases(product):
    products = product if isinstance(product, (tuple, list, set)) else (product,)
    aliases = {normalize_product_name(name) for name in products}

    # The LEI 300 table omits these words for its tea entry.
    if "ero te al limone" in aliases:
        aliases.add("total ero te al limone moneta")

    return aliases


def build_product_lookup(products):
    lookup = {}

    for code, product in products.items():
        for alias in product_aliases(product):
            existing_code = lookup.get(alias)
            if existing_code is not None and existing_code != code:
                raise ValueError(f'Produkti "{product}" ka kode qe bien ndesh.')
            lookup[alias] = code

    return lookup


def parse_quantity(value):
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        raise InvalidOperation

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        decimal_places = len(text) - text.rfind(",") - 1
        if text.count(",") == 1 and decimal_places != 3:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    return Decimal(text)


def format_quantity(quantity):
    if quantity == quantity.to_integral_value():
        return str(int(quantity))
    return format(quantity.normalize(), "f")


def process_pasted_text(text, products):
    lookup = build_product_lookup(products)
    totals = defaultdict(Decimal)
    unmatched = set()
    invalid_rows = []

    for row_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        columns = line.split("\t")
        if len(columns) < 3:
            invalid_rows.append(row_number)
            continue

        product = columns[0].strip()
        code = lookup.get(normalize_product_name(product))
        if code is None:
            unmatched.add(product)
            continue

        try:
            quantity = parse_quantity(columns[2])
        except InvalidOperation:
            invalid_rows.append(row_number)
            continue

        totals[code] += quantity

    output_lines = []
    if totals:
        total_quantity = sum(totals.values(), Decimal(0))
        output_lines.append(f"Totali: {format_quantity(total_quantity)}")
        output_lines.extend(
            f"{code}: {format_quantity(totals[code])}"
            for code in sorted(totals)
        )

    output = "\n".join(output_lines)
    return output, unmatched, invalid_rows


def choose_machine():
    print("Zgjidhni automatin:")
    for option, (name, _) in MACHINES.items():
        print(f"  {name} [{option}]")

    while True:
        choice = input("\nShkruani 1, 2, 3, 4 ose 5: ").strip()
        if choice in MACHINES:
            return MACHINES[choice]
        print("Zgjedhje e pavlefshme. Ju lutem shkruani nje numer nga 1 deri ne 5.")


def read_pasted_text():
    print("\nNgjitni 3 kolonat e Excel-it: produkti, cmimi, sasia.")
    print("Kur te perfundoni, shtypni Enter ne nje rresht bosh.\n")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break

        if not line.strip():
            break
        lines.append(line)

    return "\n".join(lines)


def ask_to_continue():
    while True:
        try:
            choice = input("\nDeshironi te vazhdoni? Po [p] Jo [j]: ").strip().casefold()
        except EOFError:
            return False

        if choice in {"p", "po", "y", "yes"}:
            return True
        if choice in {"j", "jo", "n", "no"}:
            return False
        print("Zgjedhje e pavlefshme. Ju lutem shkruani p ose j.")


def main():
    while True:
        machine_name, products = choose_machine()
        pasted_text = read_pasted_text()
        output, unmatched, invalid_rows = process_pasted_text(pasted_text, products)

        print(f"\nRezultati per {machine_name}:")
        if output:
            print(output)
        else:
            print("Nuk u gjet asnje produkt qe perputhet.")

        if unmatched:
            print(
                f"\nU injoruan {len(unmatched)} produkte qe nuk perdoren "
                f"nga {machine_name}."
            )
        if invalid_rows:
            rows = ", ".join(str(row) for row in invalid_rows)
            print(f"U anashkaluan rreshtat e pavlefshem: {rows}")

        if not ask_to_continue():
            print("Mirupafshim.")
            break
        print()


if __name__ == "__main__":
    main()

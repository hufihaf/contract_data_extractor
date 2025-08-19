import fitz
import pandas as pd
import re
import os
import argparse
from pathlib import Path

# Strings that are associated with the values on the tables
contract_number_id = "CONTRACT NO."
order_number_id = "ORDER NUMBER "
contractor_name_id = "CONTRACTOR/"
slin_id = "ITEM NO "
acrn_id = "ACRN "
unit_id = "UNIT "
quantity_id = "QUANTITY "
obligation_id = "AMOUNT "
cost_id = "UNIT PRICE "
cin_id = "CIN: "
funding_document_id = "Funding "
purchase_requisition_id = "PURCHASE REQUEST NUMBER: "
mod_contract_number_id = "MOD. OF CONTRACT/ORDER NO. "

# ---------------------------
# Detect award vs mod
# ---------------------------
def determine_document_type(document):
    first_page = document[0]
    if first_page.search_for("AMENDMENT"):
        return "mod"
    else:
        return "award"

# ---------------------------
# Find PDFs
# ---------------------------
def find_award_pdfs(root_path):
    root = Path(root_path)
    return [
        p for p in root.rglob("*.pdf") 
        if "award" in p.name.lower() or "original contract" in p.name.lower() or "mod" in p.name.lower()
    ]

def process_all_award_pdfs(input_root):
    pdf_paths = find_award_pdfs(input_root)
    print(f"Found {len(pdf_paths)} PDF(s) to process in {input_root}.\n")

    # always save outputs to Downloads/award_outputs
    output_dir = Path.home() / "Downloads" / "contract_data"
    output_dir.mkdir(exist_ok=True)

    for i, path in enumerate(pdf_paths, 1):
        try:
            doc = fitz.open(path)
        except Exception as e:
            print(f"Skipping {path} due to error: {e}")
            continue

        doc_type = determine_document_type(doc)
        print(f"[{i}/{len(pdf_paths)}] Processing {doc_type.upper()}: {path}")

        if doc_type == "mod":
            mod(doc, output_dir)
        else:
            award(doc, output_dir)

# ---------------------------
# MOD FUNCTION
# ---------------------------
def format_price(value):
    value = value.replace(",", "").strip()
    try:
        return f"${float(value):,.2f}"
    except ValueError:
        return value

def mod(document, output_dir):
    columns = ["SUBCLIN", "ACRN", "CIN", "Original Amount", "New Amount", "Difference"]
    df = pd.DataFrame(columns=columns)

    for page in document:
        text = page.get_text("text")
        pattern = re.compile(
            r"SUBCLIN\s+(\d+):\s*[\r\n]+([A-Z]{2}):.*?\(CIN\s+(\d+)\).*?"
            r"was\s+(?:increased|decreased)\s+by\s+\$([\d,]+)\s+from\s+\$?([\d,]+)\s+to\s+\$?([\d,]+)",
            re.IGNORECASE | re.DOTALL
        )

        for match in pattern.finditer(text):
            subclin = match.group(1)
            acrn = match.group(2)
            cin = match.group(3)
            diff = format_price(match.group(4))
            original = format_price(match.group(5))
            new = format_price(match.group(6))

            df = pd.concat([df, pd.DataFrame([{
                "SUBCLIN": subclin,
                "ACRN": acrn,
                "CIN": cin,
                "Original Amount": original,
                "New Amount": new,
                "Difference": diff
            }])], ignore_index=True)

    first_page = document[0]
    mod_contract_number = extract_underneath(first_page, mod_contract_number_id, dx_left=10, dx_right=10, dy=10)

    mod_contract_number = sanitize_filename(mod_contract_number)
    output_path = output_dir / f"Mod-{mod_contract_number}.csv"
    df.to_csv(output_path, index=False)
    print(f"  -> Saved {output_path}")

# ---------------------------
# AWARD FUNCTION 
# ---------------------------
def award(document, output_dir):
    columns = ["SLIN", "ACRN", "Unit", "Cost", "Qty", "Obligation", 
               "Action Type", "CIN", "Funding Doc", "Purchase Req No"]
    df = pd.DataFrame(columns=columns)

    first_page = document[0]
    contract_number = extract_underneath(first_page, contract_number_id, dx_left=3, dx_right=20, dy=8)
    order_number = extract_underneath(first_page, order_number_id, dx_left=3, dx_right=20, dy=8)

    # ---- PASS 1: Build initial table ----
    for page in document:
        slin_instances = page.search_for(slin_id)
        for slin_inst in slin_instances:
            x0, y0, x1, y1 = slin_inst
            slin_value = page.get_textbox((x0-5, y1, x1, y1+12)).strip() or ""
            search_rect = fitz.Rect(x1, y0, x1 + 500, y0 + 220)

            row_data = {
                "SLIN": slin_value,
                "ACRN": "",
                "Unit": "",
                "Cost": "",
                "Qty": "",
                "Obligation": "",
                "Action Type": "Award",
                "CIN": "",
                "Funding Doc": "",
                "Purchase Req No": ""
            }

            for attr, col_name, width, height, is_below in [
                (acrn_id, "ACRN", 20, 0, False),
                (unit_id, "Unit", 0, 15, True),
                (cost_id, "Cost", 0, 15, True),
                (cin_id, "CIN", 100, 0, False),
                (quantity_id, "Qty", 0, 8, True),
                (obligation_id, "Obligation", 50, 15, True),
                (funding_document_id, "Funding Doc", 100, 0, False),
                (purchase_requisition_id, "Purchase Req No", 60, 0, False)
            ]:
                hits = page.search_for(attr, clip=search_rect)
                if hits:
                    ax0, ay0, ax1, ay1 = hits[0]
                    if is_below:
                        value = page.get_textbox((ax0 - width, ay1, ax1, ay1 + height)).strip() or ""
                    else:
                        value = page.get_textbox((ax1, ay0, ax1 + width, ay1)).strip() or ""
                    row_data[col_name] = value

            df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

    # ---- PASS 2: Fill in missing Costs from CIN matches ----
    for idx, row in df.iterrows():
        if row["CIN"] and not row["Cost"]:
            cin_to_find = row["CIN"]
            for page in document:
                hits = page.search_for(cin_to_find)
                if hits:
                    ax0, ay0, ax1, ay1 = hits[0]
                    price = page.get_textbox((ax1, ay0, ax1 + 200, ay1)).strip()
                    if price:
                        price = sanitize_cin_value(price)
                        df.at[idx, "Cost"] = clean_cost(price)
                        break

    # Save CSV in Downloads/contract_data
    contract_number = sanitize_filename(clean_contract_or_order(contract_number))
    order_number = sanitize_filename(clean_contract_or_order(order_number))

    output_path = output_dir / f"Award {contract_number} Order {order_number}.csv"
    df.to_csv(output_path, index=False)
    print(f"  -> Saved {output_path}")

# ---------------------------
# Helpers
# ---------------------------
def extract_underneath(page, search_text, dx_left=3, dx_right=20, dy=8): # returns the text found underneath a given string on a given page.
    instance = page.search_for(search_text)
    if instance:
        x0, y0, x1, y1 = instance[0]
        return page.get_textbox((x0 - dx_left, y1, x1 + dx_right, y1 + dy)).strip()
    return ""

def sanitize_filename(value): # issue solved: "\" and quotation marks in the script argument can throw an error in the code. Output path throws an error if filename has certain characters.
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    value = re.sub(r'[\r\n\t]+', "_", value)
    return value.strip()

def clean_contract_or_order(value: str) -> str: # issue solved: unwanted characters being pulled into Contract No and Order No cells
    return re.sub(r"_\d+$", "", value)

def clean_cost(value: str) -> str: # issue solved: whitespace and colons found in Cost cells
    if not value:
        return ""
    return re.sub(r"[^$\d,\.]", "", value)

def sanitize_cin_value(string): # issue solved: multiple prices being placed into the Cost cells
    prices = re.findall(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', string)
    if len(prices) == 3:
        return prices[1]
    elif len(prices) == 2:
        return prices[0]
    else:
        return string


# Main
def main():
    parser = argparse.ArgumentParser(description="Process Award and Mod PDFs, save CSVs to Downloads.")
    parser.add_argument("input_root", help="Path to the root folder containing PDFs")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"Error: {input_root} does not exist.")
        return
    
    process_all_award_pdfs(input_root)

if __name__ == "__main__":
    main()

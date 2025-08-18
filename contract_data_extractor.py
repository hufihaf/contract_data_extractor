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


# Get all PDF files from a given root directory that contain "award" or "original contract" in the filename
def find_award_pdfs(root_path):
    root = Path(root_path)
    return [
        p for p in root.rglob("*.pdf") 
        if "award" in p.name.lower() or "original contract" in p.name.lower()
    ]


def process_all_award_pdfs(input_root):
    pdf_paths = find_award_pdfs(input_root)
    print(f"Found {len(pdf_paths)} Award PDF(s) to process in {input_root}.\n")

    # always save outputs to Downloads/award_outputs
    output_dir = Path.home() / "Downloads" / "award_outputs"
    output_dir.mkdir(exist_ok=True)

    for i, path in enumerate(pdf_paths, 1):
        try:
            doc = fitz.open(path)
        except Exception as e:
            print(f"Skipping {path} due to error: {e}")
            continue
        
        print(f"[{i}/{len(pdf_paths)}] Processing: {path}")
        award(doc, output_dir)  # save into Downloads/award_outputs


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
                        
                        # remove whitespace and any additional chars
                        df.at[idx, "Cost"] = clean_cost(price)
                        break


    # ---- Save CSV in Downloads/award_outputs ----
    contract_number = sanitize_filename(contract_number)
    order_number = sanitize_filename(order_number)
    
    # strip off trailing underscores and digits
    contract_number = clean_contract_or_order(contract_number)
    order_number = clean_contract_or_order(order_number)
    
    output_path = output_dir / f"Award {contract_number} Order {order_number}.csv"
    df.to_csv(output_path, index=False)
    print(f"  -> Saved {output_path}")


def extract_underneath(page, search_text, dx_left, dx_right, dy):
    instance = page.search_for(search_text)
    if instance:
        x0, y0, x1, y1 = instance[0]
        return page.get_textbox((x0 - dx_left, y1, x1 + dx_right, y1 + dy)).strip()
    return ""


def sanitize_filename(value):
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    value = re.sub(r'[\r\n\t]+', "_", value)
    return value.strip()

def clean_contract_or_order(value: str) -> str:
    """
    Removes any underscore and trailing digits from the contract/order number.
    Example: 'N0024418D0003_1' -> 'N0024418D0003'
             'N6339418F0035_2' -> 'N6339418F0035'
    """
    return re.sub(r"_\d+$", "", value)

def clean_cost(value: str) -> str:
    """
    Keeps only valid currency characters: $, digits, commas, and periods.
    Example: ": \n  $183,866" -> "$183,866"
    """
    if not value:
        return ""
    # Remove everything except allowed characters
    cleaned = re.sub(r"[^$\d,\.]", "", value)
    return cleaned

def sanitize_cin_value(string):
    prices = re.findall(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', string)
    if len(prices) == 3:
        return prices[1]  # middle price
    elif len(prices) == 2:
        return prices[0]  # first price
    else:
        return string


def main():
    parser = argparse.ArgumentParser(description="Process award PDFs and save CSVs to Downloads.")
    parser.add_argument("input_root", help="Path to the root folder containing PDFs")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    if not input_root.exists():
        print(f"Error: {input_root} does not exist.")
        return
    
    process_all_award_pdfs(input_root)


if __name__ == "__main__":
    main()

import fitz # this is a dependancy that needs to be downloaded
import pandas as pd
import re
import os
from pathlib import Path 
import shutil

# Strings that are associated with the values on the tables (the strings that the script needs to look for):
contract_number_id = "CONTRACT NO." # under, push left and right wall a little
order_number_id = "ORDER NUMBER " # under, push left and right wall a little
contractor_name_id = "CONTRACTOR/" # under, push left and right wall a little
slin_id = "ITEM NO " # under, a little left
acrn_id = "ACRN " # right
unit_id = "UNIT " # under
quantity_id = "QUANTITY " # under
obligation_id = "NET AMT " # right
cost_id = "UNIT PRICE " # under
cin_id = "CIN: " # right
funding_document_id = "Funding " # right
purchase_requisition_id = "PURCHASE REQUEST NUMBER: " # right


def determine_document_type(document):
    first_page = document[0]
    if first_page.search_for("AMENDMENT"):
        return "mod"
    else:
        return "award"
    
# Get all PDF files from a given root directory
def find_all_pdfs(root_path):
    root = Path(root_path)
    return list(root.rglob("*.pdf"))

def process_all_pdfs(input_root):
    pdf_paths = find_all_pdfs(input_root)
    print(f"Found {len(pdf_paths)} PDF(s) to process in {input_root}.\n")

    for i, path in enumerate(pdf_paths, 1):
        try:
            doc = fitz.open(path)
        except Exception as e:
            print(f"Skipping {path} due to error: {e}")
            continue
        
        if determine_document_type(doc) == "mod":
            mod(doc)
        elif determine_document_type(doc) == "award":
            award(doc)

# grabs the data from tables in a mod doc. Under construction
def mod(document):
    print("goomba")

def award(document):
    columns = ["SLIN", "ACRN", "Unit", "Cost", "Qty", "Obligation", "Action Type", "CIN", "Funding Doc", "Purchase Req No"]
    df = pd.DataFrame(columns=columns)

    first_page = document[0]

    # Extract contract/order/contractor names from page 1
    contract_number = extract_underneath(first_page, contract_number_id, dx=5, dy=10)
    order_number = extract_underneath(first_page, order_number_id, dx=5, dy=10)
    contractor_name = extract_underneath(first_page, contractor_name_id, dx=5, dy=10)

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
                (obligation_id, "Obligation", 200, 0, False),
                (funding_document_id, "Funding Doc", 100, 0, False),
                (purchase_requisition_id, "Purchase Req No", 60, 0, False)
            ]:
                if not attr:
                    continue

                hits = page.search_for(attr, clip=search_rect)
                if hits:
                    ax0, ay0, ax1, ay1 = hits[0]
                    if is_below:
                        value = page.get_textbox((ax0, ay1, ax1, ay1 + height)).strip() or ""
                    else:
                        value = page.get_textbox((ax1, ay0, ax1 + width, ay1)).strip() or ""
                    row_data[col_name] = value

            df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

    # PASS 2: Fill in missing Costs from CIN matches.
    # For context: CINs are associated with price values, which are identified later in the document. 
    # Pass 1 collects CINs, but NOT prices. Pass 2 collects prices and fills in the appropriate cells
    for idx, row in df.iterrows():
        if row["CIN"] and not row["Cost"]:  # CIN exists AND Cost is blank (don't want to overwrite if the table already handed us the price)
            cin_to_find = row["CIN"]

            for page in document:
                hits = page.search_for(cin_to_find)
                if hits:
                    ax0, ay0, ax1, ay1 = hits[0]
                    
                    # grab a rectangle of text to the right of the CIN. This is the price that the CIN is associated with
                    price = page.get_textbox((ax1, ay0, ax1 + 200, ay1)).strip()
                    if price:
                        price = sanitize_cin_value(price)
                        df.at[idx, "Cost"] = price
                        break

    # Save Excel file
    contract_number = sanitize_filename(contract_number)
    order_number = sanitize_filename(order_number)
    contractor_name = sanitize_filename(contractor_name)
    df.to_excel(f"{contract_number} --- {order_number} --- {contractor_name}.xlsx", index=False)


def extract_underneath(page, search_text, dx, dy):
    instance = page.search_for(search_text)
    if instance:
        x0, y0, x1, y1 = instance[0]
        return page.get_textbox((x0 - dx, y1, x1 + dx, y1 + dy)).strip()
    return ""


# This is used to avoid errors with PyMuPDF when it tries to write to Excel
def sanitize_filename(value):
    # Remove illegal filename chars on Windows:  \ / : * ? " < > | and strip spaces
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    # Replace newlines/tabs with underscore
    value = re.sub(r'[\r\n\t]+', "_", value)
    return value.strip()


# This was made to avoid the issue of multiple prices being inputted into one price cell. This issue occured because the prices are very close together in the pdf.
def sanitize_cin_value(string):
    prices = re.findall(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', string)

    if len(prices) == 3:
        return prices[1]  # middle price
    elif len(prices) == 2:
        return prices[0]  # first price
    else:
        return string # return original if 1 price or anything else


def main():
    # get the path to the directory
    input_root = ""
    while not os.path.exists(input_root):
        input_root = input("Enter the complete path to the folder that has the documents (For example, C:/Users/adam/Downloads/Data/F1): ")
        if not os.path.exists(input_root):
            print("Directory does not exist. Please try again.")
    input_root = Path(f"{input_root}")
    
    process_all_pdfs(input_root)

main()

import fitz # this is a dependancy that needs to be downloaded
import pandas as pd # ditto
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
    print("Skipping modifications for now")

# grabs the data from tables in an award doc
def award(document):
    columns = ["SLIN", "ACRN", "Unit", "Cost", "Qty", "Obligation", "Action Type", "CIN", "Funding Doc", "Purchase Req No"]
    df = pd.DataFrame(columns=columns)

    first_page = document[0]

    # Extract contract/order/contractor names from page 1
    contract_number = extract_underneath(first_page, contract_number_id, dx=5, dy=10)
    order_number = extract_underneath(first_page, order_number_id, dx=5, dy=10)
    contractor_name = extract_underneath(first_page, contractor_name_id, dx=5, dy=10)

    # Loop through pages, find SLINs
    for page in document:
        slin_instances = page.search_for(slin_id)
        for slin_inst in slin_instances:
            x0, y0, x1, y1 = slin_inst
            
            # gather the SLIN
            slin_value = page.get_textbox((x0-5, y1, x1, y1+12)).strip() or ""

            # Search rectangle to the right of SLIN (500x220 points)
            search_rect = fitz.Rect(x1, y0, x1 + 500, y0 + 220)

            # Default row values
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

            # Check each attribute inside the rectangle
            # attr = string to look for
            # col_name = the df column that we will insert our value into
            # width is the size of the scanning box (ten billion is wider than ten)
            # height is the verticle size of scan box
            # boolean at the end -> True = search below, False = search right
            
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
                    continue  # Skip if string not set

                hits = page.search_for(attr, clip=search_rect)
                if hits:
                    # Take first match ("a" is attribute)
                    ax0, ay0, ax1, ay1 = hits[0]
                    
                    # scan below attribute if value is below
                    if is_below:
                        value = page.get_textbox((ax0, ay1, ax1, ay1 + height)).strip() or ""
                        
                    # otherwise, scan right
                    else:
                        value = page.get_textbox((ax1, ay0, ax1 + width, ay1)).strip() or ""
                    row_data[col_name] = value

            df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

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


def sanitize_filename(value):
    # Remove illegal filename chars on Windows:  \ / : * ? " < > | and strip spaces
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    # Replace newlines/tabs with underscore
    value = re.sub(r'[\r\n\t]+', "_", value)
    return value.strip()


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

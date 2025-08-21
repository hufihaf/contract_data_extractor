# Contract PDF Processor Documentation

This script extracts  data from **Award** and **Modification (Mod)** contract PDFs and saves the data into CSV files.  
It was designed for semi-structured government contract PDFs where information such as SLIN, ACRN, CIN, Costs, and Obligations need to be extracted.

The script:
- Identifies whether a PDF is an **award** or a **mod** document.
- Extracts data using text-based searches (`PyMuPDF` / `fitz`).
- Cleans and standardizes extracted values.
- Saves outputs as CSV files into `~/Downloads/contract_data/`.

---

## Dependencies

- **fitz (PyMuPDF)**: PDF parsing and text extraction.
- **pandas**: Tabular data handling and CSV writing.
- **re**: Regex-based cleaning and parsing. This library is absolutely crucial to the process.
- **argparse**: Command-line argument parsing for receiving the input file location.
- **pathlib (Path)**: File path handling for writing the output.

---

## Directory and Output Behavior

- The script scans the specified `input_root` for PDFs.
- Only files with `award`, `original contract`, or `mod` in their name (case-insensitive) are processed.
- Output CSVs are always written to:

    ```~/Downloads/contract_data/```

---

## Document Type Detection

### `determine_document_type(document)`
- **Purpose:** Determines if the PDF is an award or a modification.
- **Logic:**  
  - If the first page contains `"AMENDMENT"`, classify as `"mod"`.  
  - Otherwise, classify as `"award"`.
- **Returns:** `"mod"` or `"award"`

---

## PDF Discovery and Processing

### `find_award_pdfs(root_path)`
- **Purpose:** Recursively finds relevant PDFs.
- **Logic:**  
  - Scans all `*.pdf` under `root_path`.  
  - Includes only files with `"award"`, `"original contract"`, or `"mod"` in their filename.
- **Returns:** List of `Path` objects.

---

### `process_all_award_pdfs(input_root)`
- **Purpose:** Orchestrates PDF processing for all matching files.
- **Logic:**  
  1. Calls `find_award_pdfs`.  
  2. Creates output folder `~/Downloads/contract_data`.  
  3. Iterates over PDFs.  
  4. Opens PDF with `fitz`.  
  5. Determines document type with `determine_document_type`.  
  6. Calls `mod()` for modifications, `award()` for awards.  
- **Error Handling:** Skips PDFs that fail to open.

---

## Modification Processing

### `mod(document, output_dir)`
- **Purpose:** Extracts financial changes from modification documents.
- **Columns Output:**
  - `SUBCLIN`
  - `ACRN`
  - `CIN`
  - `Original Amount`
  - `New Amount`
  - `Difference`
- **Logic:**  
  1. Iterates all pages.  
  2. Uses regex to match patterns like:  

     ```
     SUBCLIN 0001:  
     AA: ... (CIN 12345) ... was increased by $286 from $4,000 to $4,286
     ```
  3. Extracts and formats currency values with `format_price()`.  
  4. Retrieves modification contract number via `extract_underneath()`.  
  5. Saves CSV as `Mod-{ContractNumber}.csv`.

---

### `format_price(value)`
- **Purpose:** Cleans and formats numeric price values.  
- **Logic:** Removes commas, casts to float, and re-applies formatting (`$1,234.56`).  
- **Error Handling:** Returns input unchanged if conversion fails.

---

## Award Processing

### `award(document, output_dir)`
- **Purpose:** Extracts award contract line item data.  
- **Columns Output:**
  - `SLIN`
  - `ACRN`
  - `Unit`
  - `Cost`
  - `Qty`
  - `Obligation`
  - `Action Type` (always `"Award"`)
  - `CIN`
  - `Funding Doc`
  - `Purchase Req No`

- **Logic:**  
  **Pass 1:** Build table row-by-row:
  1. Locate `"ITEM NO"` (SLIN) on each page.  
  2. Extract associated fields (`ACRN`, `Unit`, `Cost`, `CIN`, `Qty`, `Obligation`, `Funding Doc`, `Purchase Req No`) from nearby bounding boxes.  
  3. Append each row to DataFrame.  

  **Pass 2:** Fix missing Costs:
  - If row has CIN but missing Cost, search entire PDF for CIN occurrence.  
  - Extract nearest price and clean it with `sanitize_cin_value()` + `clean_cost()`.  

  **Finalization:**  
  - Clean contract/order numbers with `clean_contract_or_order()` + `sanitize_filename()`.  
  - Save CSV as `Award {ContractNumber} Order {OrderNumber}.csv`.

---

## Helper Functions

### `extract_underneath(page, search_text, dx_left=3, dx_right=20, dy=8)`
- **Purpose:** Extracts text immediately underneath a given keyword.  
- **Logic:**  
  - Finds bounding box of `search_text`.  
  - Returns text from rectangle below with given offsets.  
- **Returns:** String (may be empty).

---

### `sanitize_filename(value)`
- **Purpose:** Cleans strings for safe filenames.  
- **Removes:** `\ / * ? : " < > |`  
- **Also replaces:** newline, carriage return, tab → `_`  
- **Returns:** Safe, trimmed filename.

---

### `clean_contract_or_order(value)`
- **Purpose:** Removes unwanted trailing identifiers (e.g., `_001`).  
- **Regex:** Removes `_digits` at the end.  
- **Returns:** Cleaned string.

---

### `clean_cost(value)`
- **Purpose:** Normalizes cost strings.  
- **Logic:** Removes any characters not `$`, digits, comma, or period.  
- **Returns:** Clean cost string or empty.

---

### `sanitize_cin_value(string)`
- **Purpose:** Handles multiple prices associated with CIN.  
- **Logic:**  
  - Extracts all `$x,xxx.xx` values.  
  - If 3 prices, returns middle one.  
  - If 2 prices, returns first one.  
  - Otherwise, returns raw string.  

---

## Main Script Entry

### `main()`
- **Purpose:** Command-line entry point.  
- **Arguments:**  
  - `input_root`: Path to directory containing PDFs.  
- **Logic:**  
  1. Parse `input_root`.  
  2. Validate it exists.  
  3. Call `process_all_award_pdfs(input_root)`.  

### `if __name__ == "__main__":`
- Runs `main()` when script is executed directly.

---

## Example Usage

```bash
python contract_data_extractor.py "C:/Users/YourName/Documents/Contracts"
```


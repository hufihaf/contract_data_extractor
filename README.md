# contract_data_extractor

A Python script designed to extract data from government contract PDF documents. No traditional table parsing libraries can do this out of the box. The script processes these PDFs and exports the relevant information into a csv file in your downloads folder.

## Installation

1. Clone the repository:

   ```git clone https://github.com/hufihaf/contract_data_extractor.git```
   
   ```cd contract_data_extractor```

2. Install the required dependencies:

   ```pip install PyMuPDF```
   ```pip install pandas```
   ```pip install streamlit```

## Usage

```python contract_data_extractor.py "C:/Users/name/path/to/FileWithPDFs```

Additionally, you can use the Streamlit interface:

```python -m streamlit run contract_streamlit.py```

## Documentation

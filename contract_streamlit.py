import streamlit as st
import pandas as pd
import os
from pathlib import Path

# Path to where script.py saves outputs
output_dir = Path.home() / "Downloads" / "award_outputs"

st.write("# Contract Data Tracker")

if not output_dir.exists():
    st.warning(f"No award_outputs folder found at {output_dir}. Run data extraction script then refresh the page.")
else:
    csv_files = sorted(output_dir.glob("*.csv"))

    if not csv_files:
        st.warning("No CSV files found in award_outputs.")
    else:
        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            file_base = os.path.splitext(file_name)[0]

            # Display header nicely
            if file_base.startswith("Award-"):
                st.subheader(f"Award Contract: {file_base[len('Award-'):]}")
            elif file_base.startswith("Mod-"):
                st.subheader(f"Mod Contract: {file_base[len('Mod-'):]}")
            else:
                st.subheader(file_base)

            # Load CSV as strings (so leading zeros/IDs stay intact)
            df = pd.read_csv(file_path, dtype=str)
            st.dataframe(df)
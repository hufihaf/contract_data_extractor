import streamlit as st
import pandas as pd
import os
from pathlib import Path
import re

# Path to where award & mod scripts save outputs
output_dir = Path.home() / "Downloads" / "contract_data"

st.write("# Contract Data Tracker")

def extract_contract_number(name: str) -> str:
    """
    Normalize contract number from Award/Mod filenames.
    - Ensures 'N' prefix is present.
    - Strips order/suffixes.
    """
    match = re.search(r"(\d{5}-\d{2}-[A-Z]-\d{4})", name)
    if match:
        contract = match.group(1)
        # Always ensure it starts with 'N'
        if not contract.startswith("N"):
            contract = "N" + contract
        return contract
    return name  # fallback


if not output_dir.exists():
    st.warning(f"No award_outputs folder found at {output_dir}. Run the extraction script, then refresh this page.")
else:
    csv_files = sorted(output_dir.glob("*.csv"))

    if not csv_files:
        st.warning("No CSV files found in award_outputs.")
    else:
        awards = {}
        mods = {}

        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            file_base = os.path.splitext(file_name)[0]

            if file_base.startswith("Award "):
                contract_num = extract_contract_number(file_base)
                awards[file_base] = (contract_num, file_path)
            elif file_base.startswith("Mod-"):
                contract_num = extract_contract_number(file_base)
                mods.setdefault(contract_num, []).append(file_path)

        matched_mods = set()

        # Show awards
        for award_name, (award_contract, award_path) in awards.items():
            with st.expander(f"{award_name}"):
                df_award = pd.read_csv(award_path, dtype=str)
                st.dataframe(df_award)

                related_mods = mods.get(award_contract, [])

                if related_mods:
                    st.markdown("**Associated Mods:**")
                    for mod_path in related_mods:
                        mod_name = os.path.splitext(os.path.basename(mod_path))[0]
                        matched_mods.add(mod_path)
                        with st.expander(f"{mod_name}"):
                            df_mod = pd.read_csv(mod_path, dtype=str)
                            st.dataframe(df_mod)
                else:
                    st.info("No mods found for this award.")

        # Show unmatched mods
        unmatched_mods = [p for mlist in mods.values() for p in mlist if p not in matched_mods]

        if unmatched_mods:
            st.write("---")
            st.subheader("Unmatched Mod Documents")
            for mod_path in unmatched_mods:
                mod_name = os.path.splitext(os.path.basename(mod_path))[0]
                with st.expander(f"📄 {mod_name}"):
                    df_mod = pd.read_csv(mod_path, dtype=str)
                    st.dataframe(df_mod)

import streamlit as st
import pandas as pd
import numpy as np
import json

# --- Configuration ---
# REMOVED results_file, password, advance_threshold as they are handled in main script

# --- Helper Functions ---
# REMOVED load_data and process_data - handled in main script


def style_score(score):
    if pd.isna(score):
        return "color: gray"
    elif score >= 8.5:
        return "background-color: #90EE90; color: black"
    elif score >= 7.0:
        return "background-color: #FFFFE0; color: black"
    else:
        return "background-color: #F08080; color: black"


# --- Page Logic ---
st.set_page_config(layout="wide", page_title="Browse Candidates")
st.title("Browse Candidate Evaluations")

# Check if data is loaded (assuming main script puts it in session state)
if "data_loaded" not in st.session_state or not st.session_state.data_loaded:
    st.warning("Please log in through the main page first.")
    st.stop()

df = st.session_state.df
# diversity_df = st.session_state.diversity_df # REMOVE THIS LINE

# --- Sidebar Filters ---
st.sidebar.header("Filters")

candidate_names = sorted(df["Name"].unique())
selected_names = st.sidebar.multiselect(
    "Filter by Candidate Name:", candidate_names, default=[]
)

advancement_options = {True: "Yes", False: "No"}
df["Advance Status"] = df["Advance to Top 100"].map(advancement_options)
selected_advancement = st.sidebar.multiselect(
    "Filter by Advance to Top 100:", options=["Yes", "No"], default=[]
)

filtered_df = df.copy()
if selected_names:
    filtered_df = filtered_df[filtered_df["Name"].isin(selected_names)]
if selected_advancement:
    bool_filter = filtered_df["Advance to Top 100"].apply(
        lambda x: advancement_options[x] in selected_advancement
    )
    filtered_df = filtered_df[bool_filter]

# --- Main Display ---
st.header("Filtered Results")

if filtered_df.empty:
    st.warning("No candidates match the current filter criteria.")
else:
    display_columns = [
        "Rank",
        "Name",
        "Total Score",
        "Advance to Top 100",
        "Pass Academic Threshold",
        "Summary",
    ]
    styled_df = (
        filtered_df[display_columns]
        .style.applymap(style_score, subset=["Total Score"])
        .format({"Total Score": "{:.2f}"})
    )
    st.dataframe(styled_df, use_container_width=True)
    st.markdown(f"**Total Candidates Displayed:** {len(filtered_df)}")

    st.header("View Detailed Evaluation")
    detail_candidate_name = st.selectbox(
        "Select Candidate for Detailed View:",
        options=["Select..."] + filtered_df["Name"].tolist(),
    )

    if detail_candidate_name != "Select...":
        selected_candidate_row = filtered_df[
            filtered_df["Name"] == detail_candidate_name
        ].iloc[0]
        candidate_details = selected_candidate_row["Raw Evaluation"]
        st.subheader(
            f"Detailed Evaluation for: {selected_candidate_row['Name']} (Rank: {selected_candidate_row['Rank']})"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Academic Evaluation**")
            acad_eval = candidate_details.get("AcademicEvaluation", {})
            st.metric(
                "Raw Academic Score",
                f"{acad_eval.get('TotalScore_Raw', 'N/A')} / {acad_eval.get('MaximumPossibleScore', 'N/A')}",
            )
            for key, value in acad_eval.items():
                if isinstance(value, dict):
                    st.write(f"**{key.replace('_', ' ')}**")
                    st.write(
                        f"Score: {value.get('score', 'N/A')}{' (Bonus: ' + str(value.get('bonus')) + ')' if 'bonus' in value else ''}"
                    )
                    st.caption(f"Explanation: {value.get('explanation', 'N/A')}")
                    st.markdown("---")
            st.markdown("**Final Composite Score**")
            final_composite = candidate_details.get("FinalCompositeScore", {})
            st.metric("Total Score", f"{final_composite.get('TotalScore', 'N/A')}")
            st.write("Calculation:")
            st.caption(f"Academic: {final_composite.get('AcademicComponent', 'N/A')}")
            st.caption(f"Diversity: {final_composite.get('DiversityComponent', 'N/A')}")
        with col2:
            st.markdown("**Diversity Evaluation**")
            div_eval = candidate_details.get("DiversityEvaluation", {})
            st.metric(
                "Raw Diversity Score",
                f"{div_eval.get('RawScore', 'N/A')} / {div_eval.get('MaximumPossibleScore', 'N/A')}",
            )
            st.write("Criteria Details:")
            div_details_df = pd.DataFrame(div_eval.get("CriteriaDetails", {})).T
            st.dataframe(div_details_df)
            st.markdown("**Academic Threshold Check**")
            threshold_check = candidate_details.get("AcademicThresholdCheck", {})
            passed = threshold_check.get("PassAcademicThreshold")
            pass_text = "Yes" if passed else "No" if passed is not None else "N/A"
            st.metric("Passed Academic Threshold?", pass_text)
            st.write(f"Applicant Score: {threshold_check.get('ApplicantScore', 'N/A')}")
            st.write(
                f"Minimum Required: {threshold_check.get('MinimumRequired', 'N/A')}"
            )

        st.markdown("**Overall Decision (from model)**")
        st.info(candidate_details.get("OverallDecision", "N/A"))
        st.markdown("**Summary (from model)**")
        st.info(candidate_details.get("Summary", "N/A"))
        with st.expander("View Raw Evaluation JSON"):
            st.json(candidate_details)

import streamlit as st
import json
import pandas as pd
import numpy as np
import io

# Set page config FIRST
st.set_page_config(layout="wide")

# --- Configuration ---
# Removed hardcoded file paths
PASSWORD = "hbass12345"  # Simple password protection
ADVANCE_THRESHOLD = 100

# --- Helper Functions ---


# Use st.cache_data for caching data/DataFrames
@st.cache_data
def process_and_merge_data(results_list, original_df):
    """Process JSON results and merge with original CSV DataFrame."""
    if not results_list or original_df is None:
        st.error("Missing results list or original DataFrame for processing.")
        return None

    # Filter valid results from JSON list
    valid_results = [
        r for r in results_list if r.get("status") == "success" and r.get("evaluation")
    ]
    if not valid_results:
        st.warning("No valid evaluation results found in the uploaded JSON file.")
        return None

    processed_results = []
    diversity_scores_list = []

    for result in valid_results:
        eval_data = result.get("evaluation", {})
        composite_score = eval_data.get("FinalCompositeScore", {})
        threshold_check = eval_data.get("AcademicThresholdCheck", {})
        diversity_eval = eval_data.get("DiversityEvaluation", {})
        diversity_details = diversity_eval.get("CriteriaDetails", {})

        processed_entry = {
            "ID": result.get("id", "N/A"),  # Keep ID for merging
            "Name_Eval": result.get("name", "N/A"),  # Use a distinct name temporarily
            "Total Score": composite_score.get("TotalScore", None),
            "Academic Score": threshold_check.get("ApplicantScore", None),
            "Diversity Score_Overall": diversity_eval.get("RawScore", None),
            "Summary": eval_data.get("Summary", "N/A"),
            "Pass Academic Threshold": threshold_check.get(
                "PassAcademicThreshold", None
            ),
            "Raw Evaluation": eval_data,
        }
        processed_results.append(processed_entry)

        diversity_scores_entry = {
            k: v.get("score") for k, v in diversity_details.items()
        }
        diversity_scores_entry["ID"] = result.get("id", "N/A")
        diversity_scores_list.append(diversity_scores_entry)

    results_df = pd.DataFrame(processed_results)
    diversity_scores_df = pd.DataFrame(diversity_scores_list)

    # Ensure ID is numeric for merging
    results_df["ID"] = pd.to_numeric(results_df["ID"], errors="coerce")
    diversity_scores_df["ID"] = pd.to_numeric(
        diversity_scores_df["ID"], errors="coerce"
    )
    results_df = results_df.dropna(subset=["ID"])
    diversity_scores_df = diversity_scores_df.dropna(subset=["ID"])
    results_df["ID"] = results_df["ID"].astype(int)
    diversity_scores_df["ID"] = diversity_scores_df["ID"].astype(int)

    # Merge results with original data using ID (results) and index (original_df)
    # Assuming the 'ID' in results corresponds to the original CSV row index (0-based)
    if not original_df.index.is_unique:
        st.warning("Original CSV index is not unique, resetting index for merge.")
        original_df = original_df.reset_index()
        # If the original index was meaningful, adjust merge logic, otherwise merge on 0-based index

    merged_df = pd.merge(
        results_df, original_df, left_on="ID", right_index=True, how="inner"
    )  # Use inner merge to keep only matched rows
    if merged_df.empty:
        st.error(
            "Merge between results and original data failed. Check if IDs/indices match."
        )
        return None

    # Merge diversity scores
    merged_df = pd.merge(
        merged_df, diversity_scores_df, on="ID", how="left", suffixes=("_res", "_div")
    )  # Add suffixes if any column names clash

    # --- Map Original Demographic Strings ---
    demographic_mapping = {
        "Gender_Category": "Com qual dos gêneros abaixo você se identifica?",
        "Ethnicity_Category": "Com qual das etnias abaixo você se identifica?",
        "Orientation_Category": "Qual sua orientação sexual?",
        "Region_Category": "Qual seu estado de origem?",
        "Income_Category": "Durante sua infância, qual era a renda mensal bruta do seu núcleo familiar?",
        "Schooling_Category": "Como você realizou/está realizando seus estudos de Ensino Fundamental ou equivalente?",
        "HigherEducation_Category": "Se você cursa ou já cursou ensino superior, como você realizou seus estudos?",
        "Name": "Nome completo",  # Get definitive name from CSV
    }

    for new_col, old_col in demographic_mapping.items():
        if old_col in merged_df.columns:
            merged_df[new_col] = merged_df[old_col]
        else:
            st.warning(
                f"Warning: Column '{old_col}' not found in original CSV for mapping to '{new_col}'. Statistics might be incomplete."
            )
            merged_df[new_col] = "Unknown"

    # Ensure numeric columns are numeric, coercing errors
    div_score_cols = list(diversity_scores_df.drop(columns="ID").columns)
    numeric_cols = [
        "Total Score",
        "Academic Score",
        "Diversity Score_Overall",
    ] + div_score_cols
    for col in numeric_cols:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors="coerce")

    # Sort by Total Score and add Rank/Advance columns
    merged_df = merged_df.sort_values(
        by="Total Score", ascending=False, na_position="last"
    ).reset_index(drop=True)
    merged_df["Rank"] = range(1, len(merged_df) + 1)
    merged_df["Advance to Top 100"] = merged_df["Rank"] <= ADVANCE_THRESHOLD

    # --- Final Column Selection and Renaming ---
    # Define core columns from results
    core_results_cols = [
        "ID",
        "Total Score",
        "Academic Score",
        "Diversity Score_Overall",
        "Summary",
        "Pass Academic Threshold",
        "Raw Evaluation",
        "Rank",
        "Advance to Top 100",
    ]
    # Define demographic category columns created from mapping
    demographic_category_cols = list(
        demographic_mapping.keys()
    )  # Includes 'Name' mapped from CSV
    # Define diversity score columns (excluding ID)
    div_score_cols = [col for col in diversity_scores_df.columns if col != "ID"]

    # Combine all desired columns
    final_columns_list = core_results_cols + demographic_category_cols + div_score_cols

    # Filter out columns that might not exist if merge failed partially
    final_columns = [col for col in final_columns_list if col in merged_df.columns]
    final_df = merged_df[final_columns].copy()

    # Ensure the 'Name' column is the one from the CSV mapping
    # If 'Name' is not in final_columns (because mapping failed), handle it
    if "Name" not in final_df.columns:
        st.warning(
            "Could not find definitive 'Name' column from CSV. Using name from results JSON."
        )
        if "Name_Eval" in merged_df.columns:
            final_df["Name"] = merged_df["Name_Eval"]
        else:
            final_df["Name"] = "Unknown"

    # Drop any potentially ambiguous name columns if they exist by mistake
    if "Name_Eval" in final_df.columns and "Name" in final_df.columns:
        final_df = final_df.drop(columns=["Name_Eval"])
    if "Nome completo" in final_df.columns and "Name" in final_df.columns:
        final_df = final_df.drop(columns=["Nome completo"])

    return final_df


# --- Password Check ---
def check_password():
    """Returns `True` if the user had the correct password."""
    if "password_entered" not in st.session_state:
        st.session_state.password_entered = False

    if st.session_state.password_entered:
        return True

    # Center the password input
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.subheader("Enter Password to Access Results")
        password = st.text_input("Password", type="password", key="password_input")
        submit_button = st.button("Login")

    # Check password on button click or if password is not empty
    if submit_button or (password and password == PASSWORD):
        if password == PASSWORD:
            st.session_state.password_entered = True
            # Clear the password input field after successful login
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()  # Use experimental_rerun if st.rerun is unavailable
        elif password:
            st.error("Password incorrect.")

    return False


# --- Streamlit App Main Logic ---

if not check_password():
    st.stop()  # Stop execution if password is not correct

# --- File Upload and Data Loading ---

# Initialize session state
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "df" not in st.session_state:
    st.session_state.df = None

st.sidebar.header("Upload Data Files")
uploaded_json = st.sidebar.file_uploader(
    "1. Upload Results JSON File", type="json", key="json_uploader"
)

uploaded_csv = st.sidebar.file_uploader(
    "2. Upload Original CSV File", type="csv", key="csv_uploader"
)

# Process data only if both files are uploaded
if uploaded_json is not None and uploaded_csv is not None:
    # Check if files have changed since last processing run
    # Simple check based on upload status (can be made more robust with file hashing if needed)
    if (
        not st.session_state.data_loaded
        or st.session_state.get("last_json_name") != uploaded_json.name
        or st.session_state.get("last_csv_name") != uploaded_csv.name
    ):
        st.session_state.data_loaded = False  # Reset flag for reprocessing
        st.session_state.df = None
        try:
            # Read JSON
            stringio_json = io.StringIO(uploaded_json.getvalue().decode("utf-8"))
            results_list = json.load(stringio_json)

            # Read CSV
            original_df = pd.read_csv(uploaded_csv)

            # Process and merge data
            with st.spinner("Processing and merging data..."):
                processed_df = process_and_merge_data(results_list, original_df)

            if processed_df is not None:
                st.session_state.df = processed_df
                st.session_state.data_loaded = True
                st.session_state.last_json_name = (
                    uploaded_json.name
                )  # Store names to prevent reprocessing
                st.session_state.last_csv_name = uploaded_csv.name
                st.success("Files loaded and processed successfully!")
                # Rerun needed to update pages with the new data in session state
                try:
                    st.rerun()
                except AttributeError:
                    st.experimental_rerun()
            else:
                st.error(
                    "Failed to process the uploaded files. Please check structure and content."
                )

        except json.JSONDecodeError:
            st.error("Invalid JSON file. Please upload a valid JSON file.")
        except Exception as e:
            st.error(f"An error occurred while reading or processing the files: {e}")

elif uploaded_json is not None or uploaded_csv is not None:
    st.sidebar.warning("Please upload both the JSON and CSV files.")
    st.session_state.data_loaded = (
        False  # Ensure flag is false if only one file is uploaded
    )

# --- Display Welcome/Guidance or Page Content ---
if not st.session_state.data_loaded or st.session_state.df is None:
    st.info(
        "Please upload the evaluation results JSON and the original candidate CSV files in the sidebar to view the dashboard."
    )
    st.stop()  # Don't proceed if data isn't loaded

# If data is loaded, Streamlit will automatically show the page navigation
st.sidebar.success("Data Loaded. Navigate using the sidebar.")
st.title("HBASS Mentorship Candidate Evaluation Portal")
st.markdown("--- Copyright HBASS ---")
st.info(
    "Use the sidebar to navigate between the Candidate Browser and the Overview Statistics."
)


# Note: The actual page content is in the files within the 'pages/' directory.
# Streamlit automatically detects files in 'pages/' and adds them to the sidebar.

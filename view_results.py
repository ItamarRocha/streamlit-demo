import streamlit as st
import json
import pandas as pd
import numpy as np
import io

# --- Configuration ---
# RESULTS_FILE = "analysis/results_final.json" # Removed
# ORIGINAL_CSV_FILE = "cleaned_df_new.csv" # Removed
PASSWORD = "hbass12345"  # Simple password protection
ADVANCE_THRESHOLD = 100

# --- Helper Functions ---

# Removed load_data function, parsing will happen directly from upload


# Use allow_output_mutation=True for DataFrames
@st.cache(allow_output_mutation=True)
def process_data(results_list):
    """Process loaded JSON data (list of dicts) into a pandas DataFrame."""
    if not results_list:
        return None

    processed = []
    diversity_scores_list = []

    # Filter out entries with errors or missing evaluation first
    valid_results = [
        r for r in results_list if r.get("status") == "success" and r.get("evaluation")
    ]
    if not valid_results:
        st.warning("No valid evaluation results found in the uploaded file.")
        return None

    for result in valid_results:
        eval_data = result.get("evaluation", {})
        # --- Attempt to Get Original Demographic Strings ---
        # **ASSUMPTION**: Original info might be nested. Adjust keys if needed.
        # Example: Try finding original input within the result structure.
        # We are removing the explicit CSV dependency for the upload version.
        original_info = result.get("original_input_info", {})  # Placeholder key
        if not original_info:
            # Fallback if 'original_input_info' doesn't exist - maybe it's top level?
            original_info = result

        composite_score = eval_data.get("FinalCompositeScore", {})
        threshold_check = eval_data.get("AcademicThresholdCheck", {})
        diversity_eval = eval_data.get("DiversityEvaluation", {})
        diversity_details = diversity_eval.get("CriteriaDetails", {})

        # --- Map Original Demographic Strings ---
        # **CRITICAL**: These keys MUST exist somewhere within each `result` dictionary in the uploaded JSON.
        demographic_mapping = {
            "Gender_Category": "Gender Identity",  # Example key in original_info
            "Ethnicity_Category": "Ethnicity",
            "Orientation_Category": "Sexual Orientation",
            "Region_Category": "State of Origin",
            "Income_Category": "Childhood Family Income",
            "Schooling_Category": "Primary Education Type",
            "HigherEducation_Category": "Higher Education Type",
        }
        demographic_data = {}
        found_demographics = False
        for new_col, old_key in demographic_mapping.items():
            value = original_info.get(old_key, "Unknown")
            demographic_data[new_col] = value
            if value != "Unknown":
                found_demographics = True

        processed_entry = {
            "ID": result.get("id", "N/A"),  # Keep ID if available
            "Name": result.get("name", "N/A"),
            "Total Score": composite_score.get("TotalScore", None),
            "Academic Score": threshold_check.get("ApplicantScore", None),
            "Diversity Score_Overall": diversity_eval.get("RawScore", None),
            "Summary": eval_data.get("Summary", "N/A"),
            "Pass Academic Threshold": threshold_check.get(
                "PassAcademicThreshold", None
            ),
            "Raw Evaluation": eval_data,
            **demographic_data,  # Add the extracted demographic data
        }
        processed.append(processed_entry)

        # Extract individual diversity scores
        diversity_scores_entry = {
            k: v.get("score") for k, v in diversity_details.items()
        }
        # Need a way to link these scores back if ID isn't reliable or consistent
        # Using index for now, assuming order is preserved
        diversity_scores_list.append(diversity_scores_entry)

    if not found_demographics:
        st.warning(
            "Warning: Could not find expected demographic fields in the uploaded JSON. Demographic statistics may be inaccurate or unavailable."
        )

    df = pd.DataFrame(processed)

    # Add diversity scores as columns (assuming order matches df)
    try:
        diversity_scores_df = pd.DataFrame(diversity_scores_list, index=df.index)
        df = pd.concat([df, diversity_scores_df], axis=1)
    except Exception as e:
        st.error(f"Error merging diversity scores: {e}. Check JSON structure.")
        # Continue without individual diversity scores if merge fails

    # Ensure numeric columns are numeric, coercing errors
    # Infer numeric columns dynamically if possible, but be explicit for core scores
    numeric_cols = ["Total Score", "Academic Score", "Diversity Score_Overall"] + list(
        diversity_details.keys()
    )
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort by Total Score and add Rank/Advance columns
    df = df.sort_values(
        by="Total Score", ascending=False, na_position="last"
    ).reset_index(drop=True)
    df["Rank"] = range(1, len(df) + 1)
    df["Advance to Top 100"] = df["Rank"] <= ADVANCE_THRESHOLD

    return df  # Return the final combined DataFrame


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
st.set_page_config(layout="wide")  # Set layout to wide *once* at the top

if not check_password():
    st.stop()  # Stop execution if password is not correct

# --- File Upload and Data Loading ---

# Initialize session state if not already done
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "df" not in st.session_state:
    st.session_state.df = None

uploaded_file = st.file_uploader(
    "Choose a JSON results file",
    type="json",
    accept_multiple_files=False,
    key="file_uploader",
)

if uploaded_file is not None:
    # Check if we need to reload/reprocess or if it's the same file
    # Simple approach: always reload if a file is present
    try:
        # Read content
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        results_list = json.load(stringio)

        # Process data
        processed_df = process_data(results_list)
        if processed_df is not None:
            st.session_state.df = processed_df
            st.session_state.data_loaded = True
            st.success("File loaded and processed successfully!")
            # Optional: Clear the uploader after successful processing to prevent reprocessing on every interaction
            # st.session_state.file_uploader = None # Doesn't work directly like this
            # Consider using a button to trigger processing instead of automatic rerun
        else:
            st.session_state.data_loaded = (
                False  # Ensure flag is false if processing fails
            )
            st.error(
                "Failed to process the uploaded JSON file. Please check the file structure and content."
            )

    except json.JSONDecodeError:
        st.error("Invalid JSON file. Please upload a valid JSON file.")
        st.session_state.data_loaded = False
    except Exception as e:
        st.error(f"An error occurred while reading or processing the file: {e}")
        st.session_state.data_loaded = False

# --- Display Welcome/Guidance or Page Content ---
if not st.session_state.data_loaded:
    st.info("Please upload the evaluation results JSON file to view the dashboard.")
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

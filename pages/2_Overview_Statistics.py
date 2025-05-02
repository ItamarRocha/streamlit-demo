import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px  # For charts

st.set_page_config(layout="wide", page_title="Overview Statistics")
# st.title("📊 Overview Statistics") # Title will be dynamic now

# --- Check if data is loaded ---
if "data_loaded" not in st.session_state or not st.session_state.data_loaded:
    st.warning(
        "Data not loaded. Please log in through the main page (view_results.py) first."
    )
    st.stop()

base_df = st.session_state.df  # Get the full dataframe
if base_df is None:
    st.error("Failed to load data from session state.")
    st.stop()

# --- Filter Selection ---
st.sidebar.title("Statistic Filters")
filter_option = st.sidebar.radio(
    "Select Candidate Group:",
    ("All Candidates", "Advancing to Top 100", "Not Advancing"),
)

# Filter DataFrame based on selection
if filter_option == "Advancing to Top 100":
    df = base_df[base_df["Advance to Top 100"] == True].copy()
    st.title("📊 Overview Statistics (Advancing Only)")
elif filter_option == "Not Advancing":
    df = base_df[base_df["Advance to Top 100"] == False].copy()
    st.title("📊 Overview Statistics (Not Advancing Only)")
else:  # All Candidates
    df = base_df.copy()
    st.title("📊 Overview Statistics (All Candidates)")

# Check if filtered dataframe is empty
if df.empty:
    st.warning(f"No candidates found for the filter: '{filter_option}'")
    st.stop()


# --- Calculate and Display Stats (using the filtered df) ---

st.header("Overall Performance Summary")
advancing_count = df["Advance to Top 100"].sum()
total_candidates = len(df)
not_advancing_count_filtered = (
    total_candidates - advancing_count
)  # Count within the filtered group

col1, col2, col3 = st.columns(3)
col1.metric(f"Total Candidates ({filter_option})", total_candidates)
# Show advancing/not advancing counts only if relevant to the filter
if filter_option == "All Candidates":
    col2.metric("Advancing to Top 100", advancing_count)
    col3.metric("Not Advancing", not_advancing_count_filtered)
elif filter_option == "Advancing to Top 100":
    col2.metric("Category", "Advancing")
elif filter_option == "Not Advancing":
    col2.metric("Category", "Not Advancing")


# Add overall median scores here as well
st.subheader("Overall Median Scores")
col1, col2, col3 = st.columns(3)
col1.metric("Median Total Score", f"{df['Total Score'].median():.2f}")
col2.metric("Median Academic Score (Raw)", f"{df['Academic Score'].median():.2f}")
col3.metric(
    "Median Diversity Score (Raw)", f"{df['Diversity Score_Overall'].median():.2f}"
)

st.markdown("---")
st.header("Demographic Distributions")

# Define demographic columns to analyze
demographic_cols = [
    "Gender_Category",
    "Ethnicity_Category",
    "Orientation_Category",
    "Region_Category",
    "Income_Category",
    "Schooling_Category",
    "HigherEducation_Category",
]

# Display distributions using countplots/bar charts
for col in demographic_cols:
    st.subheader(f"Distribution by {col.replace('_Category','')}")
    # Handle potential NaN/None values before counting
    counts = df[col].fillna("Unknown").value_counts()
    if not counts.empty:
        try:
            fig = px.bar(
                counts,
                x=counts.index,
                y=counts.values,
                labels={"index": col, "y": "Count"},
                title=f"Candidate Count by {col}",
            )
            fig.update_layout(xaxis_title=col, yaxis_title="Number of Candidates")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Could not generate chart for {col}: {e}")
            st.write("Data:", counts)
    else:
        st.write(f"No data available for {col}.")
    st.write(f"Counts for {col}:")
    st.dataframe(counts)
    st.markdown("---")

st.header("Median Scores by Demographic Group")

# Calculate and display median scores grouped by demographics
score_cols = ["Total Score", "Academic Score", "Diversity Score_Overall"]

for demo_col in demographic_cols:
    st.subheader(f"Median Scores by {demo_col.replace('_Category', '')}")
    try:
        # Group by the demographic column and calculate median for score columns
        median_scores = df.groupby(demo_col)[score_cols].median()
        # Format for display
        median_scores = median_scores.applymap(
            lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
        )
        st.dataframe(median_scores, use_container_width=True)
    except Exception as e:
        st.error(f"Could not calculate median scores for {demo_col}: {e}")
    st.markdown("---")

import streamlit as st
import openai
from PIL import Image
import io
import base64
import re
import gspread
import json

# Configure the OpenRouter API with your key
api_key = st.secrets["OPENROUTER_API_KEY"]
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

import gspread
import json
from google.oauth2.service_account import Credentials
import traceback
from datetime import datetime
import pandas as pd

# --- Google Sheets Connection ---
@st.cache_resource
def init_gspread_client():
    """Initializes and returns an authorized gspread client."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

def get_worksheet_by_name(_client, sheet_url, worksheet_name):
    """Gets a specific worksheet from a spreadsheet."""
    if _client is None:
        return None
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        return spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found. Please ensure it exists in your Google Sheet.")
        return None
    except Exception as e:
        st.error(f"Error opening worksheet '{worksheet_name}': {e}")
        return None

# Initialize client and get worksheets
g_client = init_gspread_client()
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ssxshfUjC9gJ_6oUyhtuoWgDizLx43-sjbqhZnAxlBo/edit?gid=0#gid=0"
counter_sheet = get_worksheet_by_name(g_client, SHEET_URL, "Counter")
feedback_sheet = get_worksheet_by_name(g_client, SHEET_URL, "Feedback")


# --- Feedback Logic ---
def add_feedback(sheet, vote, comment):
    """Adds a new row of feedback to the sheet."""
    if sheet is None:
        st.error("Could not connect to Feedback sheet. Please try again later.")
        return False
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, vote, comment])
        # Clear the cache for the feedback display function so we get fresh data
        get_all_feedback.clear()
        return True
    except Exception as e:
        st.error(f"Failed to submit feedback: {e}")
        return False

@st.cache_data(ttl=60)
def get_all_feedback(_sheet):
    """Retrieves all feedback and returns as a DataFrame."""
    if _sheet is None:
        return pd.DataFrame()
    try:
        data = _sheet.get_all_values()
        if len(data) < 2: # Only headers or empty
            return pd.DataFrame(columns=["Timestamp", "Vote", "Comment"])
        
        headers = data[0]
        df = pd.DataFrame(data[1:], columns=headers)
        return df
    except Exception as e:
        st.error(f"Failed to retrieve feedback: {e}")
        return pd.DataFrame()

counter_sheet = get_worksheet_by_name(g_client, SHEET_URL, "Counter")

def get_count(sheet):
    if sheet is None:
        return 0
    try:
        value = sheet.acell('A1').value
        if value is None:
            return 0  # If cell is empty, treat count as 0
        return int(value)
    except (ValueError, TypeError):
        # If value is not a number, reset to 0
        st.warning("Counter value in sheet was invalid. Resetting to 0.")
        sheet.update('A1', 0)
        return 0
    except Exception as e:
        st.error(f"Error getting count from sheet: {e}")
        return 0 # Return 0 on other errors

def update_count(sheet, count):
    if sheet is None:
        return
    try:
        sheet.update('A1', [[count]])
    except Exception as e:
        st.error(f"Error updating count in sheet: {e}")

# Initialize session state for the counter
if 'count' not in st.session_state:
    st.session_state.count = get_count(counter_sheet)
# --- End of Persistent Counter Setup ---


st.set_page_config(layout="wide")

# Custom CSS for styling
st.markdown("""
<style>
    /* Main app background */
    .stApp {
        background-color: #f0f2f6;
    }

    /* Left panel (for file upload) */
    [data-testid="stVerticalBlock"] {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
    }

    /* Right panel (for solution) */
    [data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e6e6e6;
    }

    /* Button style */
    .stButton>button {
        background-color: #4CAF50; /* Green */
        color: white;
        border-radius: 5px;
        border: none;
        padding: 10px 24px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        transition-duration: 0.4s;
    }

    .stButton>button:hover {
        background-color: #45a049;
    }

    /* Header and subheader colors */
    h1 {
        color: red; /* Homework Helper red */
    }
    h2, h3 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)


st.title("Homework Helper")

# Initialize session state
if 'response_text' not in st.session_state:
    st.session_state.response_text = None

left_panel, right_panel = st.columns([1, 3])

with left_panel:
    st.subheader("Upload your homework")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded homework question.", use_container_width=True)

        if st.button("Help Me!"):
            # Increment persistent counter by reading from the sheet directly
            current_count = get_count(counter_sheet)
            new_count = current_count + 1
            update_count(counter_sheet, new_count)
            st.session_state.count = new_count # Update session state for immediate display
            
            # Create the prompt
            prompt = (
                "You are a school teacher. Your task is to help students understand and solve the question in the image.\n\n"
                "Please structure your response in the following three sections:\n\n"
                "**1. Analyze Question:**\n"
                "In this section, analyze or restate the question in a way that students can easily understand. "
                "Explain what the question is asking, what information is given, and what information is missing or needs to be found.\n\n"
                "**2. Needed Knowledge Points:**\n"
                "In this section, list all the knowledge points required to solve the question as bullet points. "
                "For each knowledge point, provide a title and a detailed explanation.\n\n"
                "**3. Solve Question:**\n"
                "In this section, provide a step-by-step solution to the question with clear reasoning. Use bullet points to organize the steps."
            )

            # Prepare the image for the model
            image = Image.open(uploaded_file)
            buffered = io.BytesIO()
            image_format = uploaded_file.type.split('/')[1].upper()
            if image_format not in ['JPEG', 'PNG']:
                image_format = 'JPEG'
            image.save(buffered, format=image_format)
            img_str = base64.b64encode(buffered.getvalue()).decode()


            # Generate the content
            try:
                response = client.chat.completions.create(
#                    model="google/gemini-2.5-pro",
                    model="google/gemini-2.5-flash",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{image_format.lower()};base64,{img_str}"
                                    }
                                },
                            ],
                        }
                    ],
                )
                st.session_state.response_text = response.choices[0].message.content
            except Exception as e:
                st.error(f"An error occurred: {e}")
    
    st.markdown(f"---")
    st.write(f"Tool used: **{st.session_state.count}** times")



    # --- Feedback Section ---
    st.markdown("---")
    st.subheader("Feedback")

    # --- Display Logic ---
    if feedback_sheet:
        feedback_df = get_all_feedback(feedback_sheet)
        if not feedback_df.empty:
            valid_votes = feedback_df[feedback_df['Vote'].isin(['👍', '👎'])]
            thumbs_up_count = (valid_votes['Vote'] == '👍').sum()
            thumbs_down_count = (valid_votes['Vote'] == '👎').sum()
            st.write(f"**Overall Rating:** {int(thumbs_up_count)} 👍 | {int(thumbs_down_count)} 👎")
        else:
            st.write("No feedback submitted yet.")

    # --- Submission Logic ---
    with st.form("feedback_form", clear_on_submit=True):
        vote = st.radio(
            "Choose your rating:",
            ('👍', '👎'),
            horizontal=True,
            index=None, # Default to no selection
        )
        comment = st.text_area("Leave a comment (optional)")
        
        submitted = st.form_submit_button("Send Feedback")

        if submitted:
            if vote is None:
                st.warning("Please select a rating (👍 or 👎) before sending.")
            else:
                if add_feedback(feedback_sheet, vote, comment):
                    st.success("Thank you for your feedback!")
                    st.rerun()
                else:
                    st.error("Sorry, there was an issue submitting your feedback.")

    # --- Display Comments ---
    if feedback_sheet and 'feedback_df' in locals() and not feedback_df.empty:
        comments_df = feedback_df[feedback_df['Comment'].str.strip() != ''].copy()
        if not comments_df.empty:
            with st.expander(f"View All Comments ({len(comments_df)})"):
                comments_df_sorted = comments_df.sort_values(by="Timestamp", ascending=False)
                for index, row in comments_df_sorted.iterrows():
                    st.markdown(f"**{row['Vote']}** `({row['Timestamp']})`")
                    if row['Comment']:
                        st.info(f"{row['Comment']}")


with right_panel:
    st.header("Analysis and Solution")
    if st.session_state.response_text is None:
        st.write("The solution will be displayed here after you upload an image and click 'Help Me!'.")
    else:
        response_text = st.session_state.response_text
        
        # Find the start of each section
        analyze_start = response_text.find("1. Analyze Question")
        knowledge_start = response_text.find("2. Needed Knowledge Points")
        solve_start = response_text.find("3. Solve Question")
        
        # Extract content for each section
        if analyze_start != -1:
            # Content is from the end of the title to the start of the next section
            end_of_analyze = knowledge_start if knowledge_start != -1 else solve_start if solve_start != -1 else len(response_text)
            analyze_content = response_text[analyze_start + len("1. Analyze Question"):end_of_analyze].strip()
            with st.expander("**Analyze Question**", expanded=False):
                st.markdown(analyze_content)

        if knowledge_start != -1:
            # Content is from the end of the title to the start of the next section
            end_of_knowledge = solve_start if solve_start != -1 else len(response_text)
            knowledge_content = response_text[knowledge_start + len("2. Needed Knowledge Points"):end_of_knowledge].strip()
            with st.expander("**Needed Knowledge Points**", expanded=False):
                # The parsing for the inner expanders can remain the same
                points = re.split(r'\n\s*?[\*\-]\s', knowledge_content)
                for point in points:
                    if point.strip():
                        parts = point.split('\n', 1)
                        title = parts[0].strip()
                        if len(parts) > 1:
                            details = parts[1].strip()
                            with st.expander(title):
                                st.markdown(details)
                        else:
                            st.markdown(f"* {title}")

        if solve_start != -1:
            solve_content = response_text[solve_start + len("3. Solve Question"):
].strip()
            with st.expander("**Solve Question**", expanded=False):
                st.markdown(solve_content)

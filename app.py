import streamlit as st
import openai
from PIL import Image
import io
import base64
import re

# Configure the OpenRouter API with your key
# Note: You need to get your own API key from OpenRouter
# and set it as a secret in your Streamlit app with the key OPENROUTER_API_KEY.
api_key = st.secrets["OPENROUTER_API_KEY"]
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

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
if 'click_count' not in st.session_state:
    st.session_state.click_count = 0

left_panel, right_panel = st.columns([1, 3])

with left_panel:
    st.subheader("Upload your homework") # Changed from st.header to st.subheader
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded homework question.", use_container_width=True)

        if st.button("Help Me!"):
            st.session_state.click_count += 1 # Increment counter
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
            # Correctly determine the format, defaulting to JPEG if type is not standard
            image_format = uploaded_file.type.split('/')[1].upper()
            if image_format == 'JPEG':
                image_format = 'JPEG' # Keep it as JPEG
            elif image_format == 'PNG':
                image_format = 'PNG'
            else:
                image_format = 'JPEG' # Default to JPEG for other types
            
            image.save(buffered, format=image_format)
            img_str = base64.b64encode(buffered.getvalue()).decode()


            # Generate the content
            try:
                response = client.chat.completions.create(
                    model="google/gemini-2.5-pro",
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
    st.write(f"Tool used: **{st.session_state.click_count}** times")


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

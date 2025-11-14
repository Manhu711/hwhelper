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

st.title("Homework Helper")

# Initialize session state
if 'response_text' not in st.session_state:
    st.session_state.response_text = None

left_panel, right_panel = st.columns([1, 3])

with left_panel:
    st.header("Upload your homework")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded homework question.", use_container_width=True)

        if st.button("Help Me!"):
            # Create the prompt
            prompt = '''You are a school teacher. Your task is to help students understand and solve the question in the image.

Please structure your response in the following three sections:

**1. Analyze Question:**
In this section, analyze or restate the question in a way that students can easily understand. Explain what the question is asking, what information is given, and what information is missing or needs to be found.

**2. Needed Knowledge Points:**
In this section, list all the knowledge points required to solve the question as bullet points. For each knowledge point, provide a title and a detailed explanation.

**3. Solve Question:**
In this section, provide a step-by-step solution to the question with clear reasoning. Use bullet points to organize the steps.'''

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
 #                   model="google/gemini-2.5-flash",
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

with right_panel:
    st.header("Analysis and Solution")
    if st.session_state.response_text is None:
        st.write("The solution will be displayed here after you upload an image and click 'Help Me!'.")
    else:
        response_text = st.session_state.response_text
        st.write(response_text) # Debugging line
        
        # Use regex to find sections
        analyze_match = re.search(r'\*\*1. Analyze Question:\*\*(.*?)\*\*2. Needed Knowledge Points:\*\*', response_text, re.DOTALL)
        knowledge_match = re.search(r'\*\*2. Needed Knowledge Points:\*\*(.*?)\*\*3. Solve Question:\*\*', response_text, re.DOTALL)
        solve_match = re.search(r'\*\*3. Solve Question:\*\*(.*)', response_text, re.DOTALL)

        if analyze_match:
            with st.expander("Analyze Question", expanded=False):
                st.markdown(analyze_match.group(1).strip())

        if knowledge_match:
            with st.expander("Needed Knowledge Points", expanded=False):
                points_text = knowledge_match.group(1).strip()
                # Split by bullet points (both * and -)
                points = re.split(r'\n\s*?[\*\-]\s', points_text)
                for point in points:
                    if point.strip():
                        # The first line is the title, the rest is the details
                        parts = point.split('\n', 1)
                        title = parts[0].strip()
                        if len(parts) > 1:
                            details = parts[1].strip()
                            with st.expander(title):
                                st.markdown(details)
                        else:
                            st.markdown(f"* {title}")

        if solve_match:
            with st.expander("Solve Question", expanded=False):
                st.markdown(solve_match.group(1).strip())
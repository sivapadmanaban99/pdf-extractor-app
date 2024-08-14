import time
import pdfplumber
import PyPDF2
import csv
import streamlit as st
import boto3
import json
import pandas as pd
from botocore.exceptions import ClientError


# Function to extract tables from a PDF file
def extract_table(pdf_path):
    table_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    table_data.extend(table)
    except Exception as e:
        st.error(f"Error extracting tables: {e}")
    return table_data


# Function to extract form fields from a PDF file
def extract_form_fields(pdf_path):
    form_fields = {}
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if reader.is_encrypted:
                reader.decrypt('')
            fields = reader.get_form_text_fields()
            if fields:
                form_fields.update(fields)
    except Exception as e:
        st.error(f"Error extracting form fields: {e}")
    return form_fields


# Function to write table data to a CSV file
def tables_to_csv(table_data, csv_path):
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerows(table_data)
    except Exception as e:
        st.error(f"Error writing to CSV: {e}")


# Function to read CSV file content as a string
def read_csv_as_string(csv_path):
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            return csvfile.read()
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return ""


# Function to read questions from an Excel file
def read_questions_from_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        # Assuming the questions are in a column named 'Questions'
        return df['Questions'].dropna().tolist()
    except Exception as e:
        st.error(f"Error reading questions from Excel file: {e}")
        return []


# Function to send a prompt to an AI model and get the response
def send_prompt_to_ai_model(prompt, model_id, max_tokens, temperature):
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    }
    request = json.dumps(native_request)

    try:
        start_time = time.time()  # Record start time
        with st.spinner("Model is processing... please wait..."):
            response = client.invoke_model(modelId=model_id, body=request)
            model_response = json.loads(response["body"].read())
            response_text = model_response["content"][0]["text"]

        end_time = time.time()  # Record end time
        elapsed_time = end_time - start_time  # Calculate elapsed time
        st.info(f"Model execution completed in {elapsed_time:.2f} seconds")

        return response_text
    except (ClientError, Exception) as e:
        st.error(f"Error invoking AI model: {e}")
        return ""


# Main function to run the Streamlit app
def main():
    st.title("Compass Matrix")
    st.title("AI-Powered PDF Analyzer")

    # Sidebar for AI Model Configuration
    st.sidebar.header("AI Model Configuration")

    models = {
        "Claude 3.5 Sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
        "Claude 3 Haiku": "anthropic.claude-3-haiku-20240307-v1:0"
    }

    selected_model = st.sidebar.selectbox("Select AI Model", list(models.keys()))
    model_id = models[selected_model]
    max_tokens = st.sidebar.number_input("Max Tokens", min_value=1, max_value=32768, value=16384)
    temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=1.0, value=0.0)

    # Toggle switch for including explanation in AI model response
    include_explanation = st.sidebar.checkbox("Include Explanation", value=False)

    # File uploader for PDF files
    pdf_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    excel_file = st.file_uploader("Upload an Excel file with questions", type=["xlsx"])

    if pdf_file and excel_file:
        with open("temp.pdf", "wb") as f:
            f.write(pdf_file.getbuffer())

        st.info("Extracting tables from PDF...")
        table_data = extract_table("temp.pdf")

        if table_data:
            st.success("Tables extracted successfully!")
            csv_path = 'extracted_table_data.csv'
            tables_to_csv(table_data, csv_path)
            csv_string = read_csv_as_string(csv_path)
            print(csv_string)

            questions = read_questions_from_excel(excel_file)
            if questions:

                if (include_explanation):
                    prompt = f'you are a back-end system and can only reply in valid json format with array of objects like "postemp1", "postemp2", "postemp3" to "postemp40", and each of those postempxx items must contain an attribute called explanation, another called confidence_score and another called value which is of type float with 2 decimals.\nGiven the following tables in csv format: {csv_string} \n\n answer the following questions: \n'
                else:
                    prompt = f'you are a back-end system and can only reply in valid json format with array of objects like "postemp1", "postemp2", "postemp3" to "postemp40",and each of the object must contain an attribute called value which should be type float with 2 decimals.\nGiven the following tables in csv format: {csv_string} \n\n answer the following questions: \n'

                prompt += ''.join(questions)
                # prompt += f'Put each of those values in an attribute called value. Also explain how you got the results and which table it came from and the numeric confidence score from 0 to 100 in each response and respond in json format with keys: "value, "explanation" and "confidence_score"\n')
                if (include_explanation):
                    prompt += f'Put each of those values in an attribute called value. Also explain how you got the results and which table it came from and the numeric confidence score from 0 to 100 in each response and respond in json format with keys: "value, "explanation" and "confidence_score"\n'
                    prompt += 'and please remove the thousand seperators from the numeric value in the response'


                st.info("Sending prompt to AI model...")
                ai_response = send_prompt_to_ai_model(prompt, model_id, max_tokens, temperature)
                st.success("AI model response received!")
                st.markdown("### AI Model Response:")
                st.text(ai_response)
            else:
                st.info("Please ensure the Excel file contains questions in a 'Questions' column.")
        else:
            st.error("No tables found in the PDF.")
    else:
        st.info("Please upload a PDF and an Excel file")


if __name__ == "__main__":
    main()

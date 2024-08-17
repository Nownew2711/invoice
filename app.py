import gradio as gr
from pdf2image import convert_from_path
import pytesseract
import pandas as pd
import re
import logging

def process_pdf(file):
    try:
        # Check if the file is a PDF
        if not file.name.lower().endswith('.pdf'):
            logging.warning("Uploaded file is not a PDF.")
            return "Error: Uploaded file is not a PDF. Please upload a PDF file.", None
        
        images = convert_from_path(file.name)
        full_text = ""
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img)
            logging.debug(f"Text extracted from image {i+1}: {text[:100]}...")
            full_text += text + "\n"
        
        if not full_text.strip():
            logging.error("No text could be extracted from the PDF.")
            return "Error: Unable to extract text. The PDF might be blank or incorrectly formatted.", None
        
        required_keywords = ['invoice', 'order no', 'invoice date', 'supplier name', 'warehouse id']
        if not any(keyword in full_text.lower() for keyword in required_keywords):
            return "Error: The uploaded PDF does not contain necessary fields like 'Invoice', 'Order No', etc. Please upload a correct invoice.", None
        
        csv_data = save_to_csv(full_text)
        csv_path = "output.csv"
        with open(csv_path, "w") as f:
            f.write(csv_data)
        
        return "Processing Complete", csv_path  # Return the file path
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}", None

def extract_fields(text):
    invoice_no = re.search(r'Invoice No:\s*([A-Z0-9-]+)', text)
    order_no = re.search(r'HM Order No:\s*(\d+)', text)
    invoice_date = re.search(r'Invoice Date:\s*([\d-]+)', text)
    supplier_name = re.search(r'Supplier Name:\s*([A-Z\s]+)', text)
    warehouse_id = re.search(r'\bINW\d{3}\b', text)
    
    description_of_goods = None
    if warehouse_id:
        warehouse_line_start = text.find(warehouse_id.group(0))
        description_lines = []
        lines = text[warehouse_line_start:].split('\n')
        for line in lines:
            if "Container No:" in line:
                break
            description_lines.append(line.strip())
        description = ' '.join(description_lines).replace(' Cartons', '')
        words = description.split()
        filtered_words = [
            word for word in words
            if not re.match(r'^\d+(\.\d+)?$', word) and word.lower() not in ['usd', 'pieces'] and '=' not in word and word != warehouse_id.group(0)
        ]
        description_of_goods = ' '.join(filtered_words)

    return {
        'Invoice No': invoice_no.group(1) if invoice_no else None,
        'HM Order No': order_no.group(1) if order_no else None,
        'Invoice Date': invoice_date.group(1) if invoice_date else None,
        'Supplier Name': supplier_name.group(1).strip() if supplier_name else None,
        'Warehouse ID': warehouse_id.group(0) if warehouse_id else None,
        'Description of Goods': description_of_goods
    }

def save_to_csv(full_text):
    invoice_texts = full_text.split('INVOICE')
    data = []

    for i in range(1, len(invoice_texts)):
        invoice_text = "INVOICE" + invoice_texts[i]
        fields = extract_fields(invoice_text)
        if fields['Invoice No']:
            data.append(fields)

    df_invoices = pd.DataFrame(data)

    # Function to fix hanging words and capitalize text
    def fix_description(description):
        words = description.split()
        fixed_words = []
        for i in range(len(words) - 1):
            if len(words[i + 1]) <= 2:
                fixed_words.append(words[i] + words[i + 1])
            else:
                if len(words[i]) > 2:
                    fixed_words.append(words[i])
        if len(words[-1]) > 1:
            fixed_words.append(words[-1])

        return " ".join(fixed_words).upper()

    df_invoices['Description of Goods'] = df_invoices['Description of Goods'].apply(fix_description)

    csv_data = df_invoices.to_csv(index=False)
    return csv_data

iface = gr.Interface(
    fn=process_pdf,
    inputs=gr.File(file_types=['.pdf']),
    outputs=[gr.Textbox(), gr.File(label="Download CSV")]
)

iface.launch()

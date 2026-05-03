import os
import json
import logging
import io
import pandas as pd
from django.conf import settings
import google.generativeai as genai
from PIL import Image

# Setup logger
logger = logging.getLogger(__name__)

# Configure Groq
groq_api_key = getattr(settings, 'GROQ_API_KEY', None)
try:
    from groq import Groq
    groq_client = Groq(api_key=groq_api_key, timeout=30.0) if groq_api_key else None
except ImportError:
    groq_client = None

def extract_financial_data(file_content, file_type):
    """
    Uses Gemini AI to extract financial data from a variety of file types.
    Supports: Images, PDF, Excel, CSV.
    Returns a dict compatible with FinancialRecord fields.
    """
    if not groq_client:
        return {"error": "GROQ_API_KEY is not configured in settings."}

    try:
        prompt = """
        Analyze this financial document (invoice/receipt/spreadsheet) and extract the following data in JSON format:
        {
            "date": "YYYY-MM-DD",
            "revenue": float,
            "expenses": float,
            "cogs": float,
            "taxes": float,
            "currency": "string",
            "confidence": float (0-1),
            "alerts": ["list of strings for mistakes or suspicious data"]
        }
        
        Rules:
        1. If it's a sales invoice, map the total to 'revenue'. 
        2. If it's a purchase bill or expense receipt, map it to 'expenses'.
        3. 'cogs' is Cost of Goods Sold if mentioned.
        4. Detect mistakes: 
           - Alert if calculated Net Profit is negative.
           - Alert if tax rate is unusually high (> 20%).
           - Alert if any numbers are illegible.
        5. Output ONLY raw JSON, with no markdown tags like ```json.
        """

        response_content = None

        if 'image' in file_type:
            gemini_api_key = getattr(settings, 'GOOGLE_API_KEY', None)
            if gemini_api_key:
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")

                response = model.generate_content([
                    {"mime_type": file_type, "data": file_content},
                    prompt
                ])
                response_content = response.text.strip()
            else:
                return {"error": "GOOGLE_API_KEY is missing."}

            
        # 2. Handle PDF (Extract text, send to text model)
        elif file_type == 'application/pdf':
            import pdfplumber
            pdf_text = []
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages[:5]: # First 5 pages max
                    text = page.extract_text()
                    if text:
                        pdf_text.append(text)
            text_data = "\n".join(pdf_text)
            
            response = groq_client.chat.completions.create(
                model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[
                    {"role": "user", "content": f"{prompt}\n\nDOCUMENT TEXT:\n{text_data}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            response_content = response.choices[0].message.content

        # 3. Handle Spreadsheets (Convert to text context, send to text model)
        elif 'csv' in file_type or 'excel' in file_type or 'spreadsheet' in file_type:
            try:
                if 'csv' in file_type:
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
                
                # Convert first 50 rows of data to a text representation for the prompt
                tabular_text = df.head(50).to_string()
                response = groq_client.chat.completions.create(
                    model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\nDATA TO ANALYZE (First 50 rows):\n{tabular_text}"}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                response_content = response.choices[0].message.content
            except Exception as e:
                return {"error": f"فشل قراءة ملف البيانات: {str(e)}"}

        else:
            return {"error": f"نوع الملف ({file_type}) غير مدعوم حالياً للفحص المالي الذكي."}

        if not response_content:
            return {"error": "فشل المحرك الذكي في معالجة المستند."}

        # Parse JSON from response
        text_response = response_content.strip()
        # Remove markdown code blocks if present
        import re
        json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
        if json_match:
            text_response = json_match.group(0)
            
        return json.loads(text_response)

    except Exception as e:
        logger.error(f"AI Extraction Error: {str(e)}")
        return {"error": f"فشل الفحص الذكي: {str(e)}"}

def validate_extraction(data):
    """
    Additional server-side business logic validation.
    """
    alerts = data.get('alerts', [])
    revenue = data.get('revenue', 0) or 0
    expenses = data.get('expenses', 0) or 0
    taxes = data.get('taxes', 0) or 0
    
    if revenue > 0 and expenses > (revenue * 0.9):
        alerts.append("تحذير: المصاريف مرتفعة جداً مقارنة بالإيرادات (أكثر من 90%).")
    
    if taxes > 0 and revenue > 0 and (taxes / revenue) > 0.25:
        alerts.append("تنبيه: نسبة الضرائب مرتفعة بشكل غير معتاد (> 25%).")
        
    data['alerts'] = alerts
    return data

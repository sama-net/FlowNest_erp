# FlowNest ERP — Financial Dashboard

داشبورد مالي متكامل بمصدرين للبيانات.

---

## التثبيت

```bash
pip install -r requirements.txt
```

لقراءة PDF يلزمك أيضاً:
```bash
# Linux / Mac
sudo apt-get install tesseract-ocr imagemagick

# Windows
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# ImageMagick: https://imagemagick.org/script/download.php#windows
```

---

## التشغيل

```bash
python app.py
```

ثم افتح المتصفح على: **http://localhost:5050**

---

## المصدر الأول — ملفات محلية

### الطريقة 1: عدّل الكود مباشرة
```python
FILE_PATHS = [
    r"C:\Reports\q1_2024.csv",
    r"C:\Reports\q2_2024.xlsx",
    r"C:\Scans\invoice.pdf",
]
```

### الطريقة 2: من الداشبورد
- اذهب لـ **الإعدادات** ← **مسارات الملفات**
- اكتب المسارات واضغط **حفظ**
- اضغط **تحميل البيانات**

### الأعمدة المطلوبة في CSV/Excel
| العمود | البديل المقبول |
|--------|--------------|
| period | month / quarter / name |
| revenue | sales / total_income |
| cogs | cost_of_goods_sold |
| expenses | total_expenses |
| taxes | income_tax |
| interest | *(اختياري)* |
| depreciation | *(اختياري)* |

---

## المصدر الثاني — PostgreSQL

### الطريقة 1: عدّل الكود مباشرة
```python
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "your_database",
    "user":     "your_user",
    "password": "your_password",
}

DB_QUERY = """
    SELECT period, revenue, cogs, expenses, taxes
    FROM financial_data
    ORDER BY period;
"""
```

### الطريقة 2: من الداشبورد
- اذهب لـ **الإعدادات** ← **إعدادات PostgreSQL**
- أدخل بيانات الاتصال والـ Query
- اضغط **حفظ وتطبيق** ثم **تحميل البيانات**

---

## الشارتات الموجودة

| الشارت | الوصف |
|--------|-------|
| Bar Chart | الإيرادات vs COGS vs المصروفات |
| Line Chart | صافي الربح عبر الفترات |
| Margin Lines | هامش إجمالي وصافي % |
| EBITDA Bar | EBITDA مقابل صافي الربح |
| Waterfall | تحليل آخر فترة من الإيرادات لصافي الربح |
| Donut | توزيع التكاليف بالنسب |

---

## API Endpoints

| Endpoint | الوصف |
|----------|-------|
| `GET /api/data/files` | تحميل البيانات من الملفات |
| `GET /api/data/db` | تحميل البيانات من PostgreSQL |
| `POST /api/config/files` | تحديث مسارات الملفات |
| `POST /api/config/db` | تحديث إعدادات الداتابيز |

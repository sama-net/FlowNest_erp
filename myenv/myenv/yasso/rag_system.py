"""
╔══════════════════════════════════════════════════════════════╗
║         ERP RAG System - Financial & Production Data         ║
║         Built with Groq LLM + ChromaDB Vector Store          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import threading
import time
from datetime import datetime

import django
from django.conf import settings as django_settings

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
CHROMA_CFG   = django_settings.CHROMADB
CHROMA_PATH  = str(CHROMA_CFG["PERSIST_DIRECTORY"])
COLLECTION   = CHROMA_CFG["COLLECTION_NAME"]
DISTANCE     = CHROMA_CFG["DISTANCE_METRIC"]
TOP_K        = CHROMA_CFG["TOP_K"]

GROQ_API_KEY = django_settings.GROQ_API_KEY
GROQ_MODEL   = django_settings.GROQ_MODEL

# Single global lock — prevents concurrent ChromaDB + ONNX model loading
MODEL_LOAD_LOCK = threading.Lock()
_GLOBAL_CHROMA_CLIENT = None
_GLOBAL_CHROMA_COLLECTION = None
_INDEXING_STARTED = False


# ─────────────────────────────────────────────
#  RAG SYSTEM CLASS
# ─────────────────────────────────────────────
class ERPRagSystem:
    """
    Professional RAG System for ERP Financial & Production Data.
    Architecture:
        1. Data Ingestion → DB rows → Chunking → ChromaDB (local ONNX embeddings)
        2. Query → Semantic Search → Context Assembly
        3. Groq LLM (llama3-70b) → Final Answer
    """

    def __init__(self):
        self.chroma_client   = None
        self.collection      = None
        self.groq_client     = None
        self._init_llm()
        self._init_vector_store()
        
        # Background indexing: ONLY start once, and ONLY after ChromaDB is ready
        global _INDEXING_STARTED
        if not _INDEXING_STARTED and self.collection is not None:
            _INDEXING_STARTED = True
            threading.Thread(target=self._background_index, daemon=True).start()

    # ── LLM Init ──────────────────────────────────────────────
    def _init_llm(self):
        """Initialize Groq client with a timeout to prevent hanging."""
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=GROQ_API_KEY, timeout=30.0)
        except Exception as e:
            print(f"GROQ INIT FAILED: {e}")
            self.groq_client = None

    # ── ChromaDB Init ──────────────────────────────────────────
    def _init_vector_store(self):
        global _GLOBAL_CHROMA_CLIENT, _GLOBAL_CHROMA_COLLECTION
        with MODEL_LOAD_LOCK:
            if _GLOBAL_CHROMA_CLIENT is not None:
                self.chroma_client = _GLOBAL_CHROMA_CLIENT
                self.collection = _GLOBAL_CHROMA_COLLECTION
                return
            try:
                import chromadb
                from chromadb.config import Settings
                settings = Settings(
                    anonymized_telemetry=False,
                    is_persistent=True,
                    persist_directory=CHROMA_PATH
                )
                _GLOBAL_CHROMA_CLIENT = chromadb.PersistentClient(
                    path=CHROMA_PATH,
                    settings=settings
                )
                _GLOBAL_CHROMA_COLLECTION = _GLOBAL_CHROMA_CLIENT.get_or_create_collection(
                    name=COLLECTION,
                    metadata={"hnsw:space": DISTANCE}
                )
                self.chroma_client = _GLOBAL_CHROMA_CLIENT
                self.collection = _GLOBAL_CHROMA_COLLECTION
                print("ChromaDB initialized successfully.")
            except Exception as e:
                print(f"CHROMADB INIT FAILED: {e}")
                self.chroma_client = None
                self.collection = None

    # ── Background Indexing ───────────────────────────────────
    def _background_index(self):
        """
        Runs in a background thread after startup.
        Waits 10 seconds to let the server warm up fully,
        then indexes DB records ONLY if the collection is empty.
        """
        time.sleep(10)
        try:
            if self.collection and self.collection.count() == 0:
                print("RAG: Starting initial DB index...")
                self._load_from_db()
                print("RAG: Initial DB index complete.")
        except Exception as e:
            print(f"RAG Background Index Error: {e}")

    # ── DB → ChromaDB seeding ─────────────────────────────────
    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> list:
        words = text.split()
        chunks, i = [], 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += chunk_size - overlap
        return chunks

    def _load_from_db(self):
        """Read every Profile + DataFile from DB and upsert into ChromaDB."""
        from products.models import Profile, DataFile

        for profile in Profile.objects.select_related("user").all():
            doc_text = (
                f"Company: {profile.company_name}\n"
                f"Industry: {profile.industry}\n"
                f"Description: {profile.company_description}\n"
                f"Department: {profile.department}\n"
                f"Role: {profile.role}\n"
                f"Plan: {profile.plan}"
            )
            self._upsert_chunks(
                doc_id=f"profile_{profile.pk}",
                text=doc_text,
                metadata={
                    "type": "company_profile",
                    "company": str(profile.company.name) if profile.company else str(profile.company_name),
                    "department_id": str(profile.department.id) if profile.department else "None",
                    "department": str(profile.department.name) if profile.department else "General",
                    "user": str(profile.user.username),
                    "profile_id": str(profile.pk),
                },
            )

        from products.models import FinancialRecord, CompanyEconomics
        for fin in FinancialRecord.objects.all():
            doc_text = (
                f"تقرير مالي (سجل الأرباح والخسائر) بتاريخ: {fin.date}\n"
                f"الإيرادات الإجمالية: {fin.revenue}\n"
                f"المصروفات التشغيلية: {fin.expenses}\n"
                f"تكلفة المبيعات (COGS): {fin.cogs}\n"
                f"الضرائب المستحقة: {fin.taxes}\n"
                f"صافي الربح النهائي (Profit): {fin.net_profit}\n"
                f"ملخص مالي للشركة: {fin.company_name}"
            )
            self._upsert_chunks(
                doc_id=f"fin_record_{fin.pk}",
                text=doc_text,
                metadata={
                    "type": "financial_record",
                    "company": str(fin.company.name) if fin.company else str(fin.company_name),
                },
            )

        for econ in CompanyEconomics.objects.all():
            doc_text = (
                f"التحليل المالي المتقدم والتقييم الاستراتيجي (Advanced Financial Analysis):\n"
                f"إجمالي الأسهم المصدرة: {econ.total_shares}\n"
                f"سعر السهم الحالي: {econ.share_price}\n"
                f"إجمالي قيمة الأصول: {econ.assets_value}\n"
                f"إجمالي الالتزامات المالية: {econ.liabilities_value}\n"
                f"القيمة السوقية الكلية (Market Cap): {econ.market_cap}\n"
                f"مضاعف الصناعة: {econ.industry_multiplier}\n"
                f"الشركة المستهدفة: {econ.company_name}"
            )
            self._upsert_chunks(
                doc_id=f"company_economics_{econ.pk}",
                text=doc_text,
                metadata={
                    "type": "company_economics",
                    "company": str(econ.company.name) if econ.company else str(econ.company_name),
                },
            )

        for df in DataFile.objects.all():
            if df.file_type in ("pdf", "excel", "csv", "jpg", "png", "jpeg", "other"):

                time.sleep(0.2)  # Yield GIL between files — prevents server freeze
                file_text = self._extract_file_text(df)
                if file_text:
                    self._upsert_chunks(
                        doc_id=f"file_{df.pk}",
                        text=file_text,
                        metadata={
                            "type": str(df.file_type),
                            "department_id": str(df.department.id) if df.department else "None",
                            "source_department": str(df.source_department or "Direct"),
                            "target_department": str(df.target_department or "General"),
                            "user": str(df.uploaded_by.username),
                            "file_id": str(df.pk),
                            "file_name": os.path.basename(df.file.name),
                            "uploaded_at": df.uploaded_at.isoformat(),
                            "company": str(df.uploaded_by.profile.company_name) if hasattr(df.uploaded_by, 'profile') and df.uploaded_by.profile else "General",
                        },
                    )


    def _extract_file_text(self, company_file) -> str:
        """Best-effort text extraction from uploaded files."""
        try:
            file_path = company_file.file.path
            if not os.path.exists(file_path):
                return ""
            if company_file.file_type == "pdf":
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages[:5])
            elif company_file.file_type == "excel":
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
                rows = []
                for ws in wb.worksheets:
                    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                        if row_idx > 500:
                            break
                        rows.append(" | ".join(str(c) for c in row if c is not None))
                wb.close()
                return "\n".join(rows)
            elif company_file.file_type == "csv":
                import csv
                rows = []
                with open(file_path, newline='', encoding='utf-8', errors='replace') as f:
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i > 500:
                            break
                        rows.append(" | ".join(row))
                return "\n".join(rows)
            elif company_file.file_type in ("jpg", "png", "jpeg"):
                # Use Groq vision to describe the image for indexing
                try:
                    gemini_api_key = getattr(django_settings, 'GOOGLE_API_KEY', None)
                    if gemini_api_key:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_api_key)
                        model = genai.GenerativeModel("gemini-2.5-flash")

                        with open(file_path, "rb") as img_f:
                            img_data = img_f.read()
                        resp = model.generate_content([
                            {"mime_type": "image/jpeg" if "jpg" in company_file.file_type or "jpeg" in company_file.file_type else "image/png", "data": img_data},
                            "Describe this business document or image in detail for ERP context."
                        ])
                        return f"[IMAGE]: {resp.text}"
                except Exception as e:
                    return f"[IMAGE ERROR]: {str(e)}"
            elif company_file.file_type == "other":
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read(5000)
                except:
                    return f"[Binary/Other file format: {company_file.file.name}]"


        except Exception as e:
            print(f"Extraction Error for file {company_file.pk}: {e}")
        return ""

    def _upsert_chunks(self, doc_id: str, text: str, metadata: dict):
        if not self.collection:
            return
        chunks = self._chunk_text(text)
        if not chunks:
            return
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{idx}"
            try:
                self.collection.upsert(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{**metadata, "chunk_index": idx, "source_id": doc_id}],
                )
                time.sleep(0.02)  # Yield GIL between upserts
            except Exception as e:
                print(f"UPSERT ERROR chunk {chunk_id}: {e}")

    # ── Query ─────────────────────────────────────────────────
    def retrieve(self, query: str, top_k: int = TOP_K, **kwargs) -> list:
        if not self.collection:
            return []
        try:
            where_filter = None
            conditions = []
            if kwargs.get('company'):
                conditions.append({"company": kwargs['company']})
            if kwargs.get('department_id'):
                conditions.append({"department_id": str(kwargs['department_id'])})
            if len(conditions) == 1:
                where_filter = conditions[0]
            elif len(conditions) > 1:
                where_filter = {"$and": conditions}

            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, max(1, self.collection.count())),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
            chunks = []
            for i, doc in enumerate(results["documents"][0]):
                chunks.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i],
                    "score": 1 - results["distances"][0][i],
                })
            return sorted(chunks, key=lambda x: x["score"], reverse=True)
        except Exception as e:
            print(f"RAG Retrieve Error: {e}")
            return []

    def query(self, question: str, **kwargs) -> dict:
        if not self.groq_client:
            return {"answer": "المساعد الذكي غير متاح حالياً. تحقق من إعدادات GROQ_API_KEY.", "sources": []}
        
        chunks = self.retrieve(question, **kwargs)
        context_text = ""
        for i, chunk in enumerate(chunks, 1):
            context_text += f"\n[Source {i}] {chunk['content']}\n"

        if not context_text.strip():
            context_text = "لا توجد ملفات أو بيانات مفهرسة للشركة بعد."

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = (
            "You are a professional ERP financial and production analyst for an Arabic-speaking company. "
            f"The current date and time is {now}.\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer based ONLY on the provided context and financial records.\n"
            "2. PRIORITIZE information from 'التحليل المالي المتقدم' and 'سجل الأرباح والخسائر' when asked about profits, valuation, or company performance.\n"
            "3. If the answer is not in the context, state that you don't have this specific information yet.\n"
            "4. IMPORTANT: ALWAYS use professional Arabic (Fusha) for your final response.\n"
            "5. IGNORE any garbled or random text in the Context (these are just PDF/Excel extraction errors). Focus on the readable Arabic/English text and numbers.\n"
            "6. For financial data, be precise (numbers and dates).\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

        response = self.groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        return {
            "question": question,
            "answer": response.choices[0].message.content,
            "sources": [{**c["metadata"], "source_text": c["content"][:150]} for c in chunks],

            "timestamp": datetime.now().isoformat(),
        }

    def simple_chat(self, question: str) -> dict:
        if not self.groq_client:
            return {"answer": "المساعد الذكي غير متاح حالياً."}
        response = self.groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful ERP assistant. Answer professionally. Reply in the same language as the user."},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return {"answer": response.choices[0].message.content}

    def extract_smart_data(self, text: str, file_type: str) -> dict:
        if not text or not self.groq_client:
            return {}
        try:
            prompt = (
                "Extract structured fields from this ERP document text. "
                "Return ONLY a clean JSON object with these keys: "
                "vendor, amount (number), date (YYYY-MM-DD), currency, type, summary (in Arabic). "
                f"\n\nText:\n{text[:4000]}"
            )
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"AI Extraction Error: {e}")
            return {"error": str(e)}

    def sync_file(self, df):
        """Called when a new file is uploaded. Index it immediately."""
        if df.file_type in ("pdf", "excel", "csv", "jpg", "png", "jpeg"):
            file_text = self._extract_file_text(df)
            if file_text:
                self._upsert_chunks(
                    doc_id=f"file_{df.pk}",
                    text=file_text,
                    metadata={
                        "type": str(df.file_type),
                        "file_id": str(df.pk),
                        "company": str(df.uploaded_by.profile.company_name) if hasattr(df.uploaded_by, 'profile') else "General",
                        "department_id": str(df.department.id) if df.department else "None",
                        "user": str(df.uploaded_by.username),
                        "uploaded_at": df.uploaded_at.isoformat() if hasattr(df, 'uploaded_at') and df.uploaded_at else datetime.now().isoformat(),
                    }
                )
                if not df.analysis_result:
                    df.analysis_result = self.extract_smart_data(file_text, df.file_type)
                    if df.analysis_result and df.analysis_result.get('amount'):
                        try:
                            df.linked_cost = float(df.analysis_result['amount'])
                        except Exception:
                            pass
            df.is_synced = True
            df.save()

    def sync_db(self):
        """Force re-index all DB records. Called from admin sync endpoint."""
        self._load_from_db()

    def sync_financial_record(self, fin):
        """Called when a FinancialRecord is created or updated."""
        doc_text = (
            f"تقرير مالي (سجل الأرباح والخسائر) بتاريخ: {fin.date}\n"
            f"الإيرادات الإجمالية: {fin.revenue}\n"
            f"المصروفات التشغيلية: {fin.expenses}\n"
            f"تكلفة المبيعات (COGS): {fin.cogs}\n"
            f"الضرائب المستحقة: {fin.taxes}\n"
            f"صافي الربح النهائي (Profit): {fin.net_profit}\n"
            f"ملخص مالي للشركة: {fin.company_name}"
        )
        self._upsert_chunks(
            doc_id=f"fin_record_{fin.pk}",
            text=doc_text,
            metadata={
                "type": "financial_record",
                "company": str(fin.company.name) if fin.company else str(fin.company_name),
            },
        )

    def sync_company_economics(self, econ):
        """Called when a CompanyEconomics is created or updated."""
        doc_text = (
            f"التحليل المالي المتقدم والتقييم الاستراتيجي (Advanced Financial Analysis):\n"
            f"إجمالي الأسهم المصدرة: {econ.total_shares}\n"
            f"سعر السهم الحالي: {econ.share_price}\n"
            f"إجمالي قيمة الأصول: {econ.assets_value}\n"
            f"إجمالي الالتزامات المالية: {econ.liabilities_value}\n"
            f"القيمة السوقية الكلية (Market Cap): {econ.market_cap}\n"
            f"مضاعف الصناعة: {econ.industry_multiplier}\n"
            f"الشركة المستهدفة: {econ.company_name}"
        )
        self._upsert_chunks(
            doc_id=f"company_economics_{econ.pk}",
            text=doc_text,
            metadata={
                "type": "company_economics",
                "company": str(econ.company.name) if econ.company else str(econ.company_name),
            },
        )
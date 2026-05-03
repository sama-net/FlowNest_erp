from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Shared executor for background tasks to prevent process exhaustion
_executor = ThreadPoolExecutor(max_workers=4)

def enqueue_task(func, *args, **kwargs):
    """
Enqueues a function to be executed in the background pool.
    """
    try:
        _executor.submit(func, *args, **kwargs)
        logger.info(f"Task {func.__name__} enqueued successfully.")
    except Exception as e:
        logger.error(f"Failed to enqueue task {func.__name__}: {e}")

def sync_file_to_rag_task(file_id):
    """
    Background worker for RAG synchronization.
    """
    try:
        # Import inside to avoid circular deps
        from rag_system import ERPRagSystem
        from products.models import DataFile
        
        target_df = DataFile.objects.get(pk=file_id)
        rag = ERPRagSystem()
        rag.sync_file(target_df)
        
        # Mark as analyzed if needed
        # target_df.analysis_result = {"status": "synced"}
        # target_df.save()
        
    except Exception as e:
        logger.error(f"Background RAG sync error for file {file_id}: {e}")
    finally:
        from django.db import connection
        connection.close()

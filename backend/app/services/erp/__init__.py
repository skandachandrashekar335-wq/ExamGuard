"""ERP service layer for ExamGuard.

Provides synchronization with external ERP systems via the adapter pattern.
"""

from app.services.erp.adapter import ErpAdapter, ErpSyncLog
from app.services.erp.service import ErpSyncService
from app.services.erp.service import ErpSyncService
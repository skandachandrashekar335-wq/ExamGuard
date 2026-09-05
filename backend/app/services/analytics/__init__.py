"""Analytics service layer for ExamGuard.

Provides read-only aggregation and reporting over the existing domain
models. All functions are observational only — no business logic
mutations, no authorization, no data fabrication.

Use SQL-level aggregation wherever possible. Prefer live SQL queries
over Python-side processing of entire tables.
"""

from app.services.analytics.attendance import *
from app.services.analytics.verification import *
from app.services.analytics.proxy_risk import *
from app.services.analytics.hall_utilization import *
from app.services.analytics.exam_statistics import *
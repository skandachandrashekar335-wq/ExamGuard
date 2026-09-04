import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SecuritySignalType(str, enum.Enum):
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    UNUSUAL_ENTRY_POINT = "UNUSUAL_ENTRY_POINT"
    UNUSUAL_TIME = "UNUSUAL_TIME"
    SEAT_MISMATCH = "SEAT_MISMATCH"
    MULTIPLE_REGISTRATIONS = "MULTIPLE_REGISTRATIONS"
    RAPID_ENTRY = "RAPID_ENTRY"
    DOCUMENT_ANOMALY = "DOCUMENT_ANOMALY"
    BEHAVIORAL_ANOMALY = "BEHAVIORAL_ANOMALY"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    MANUAL_FLAG = "MANUAL_FLAG"


class SignalStrength(str, enum.Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INFORMATIONAL = "INFORMATIONAL"


SIGNAL_STRENGTH_DEFAULTS: dict[str, SignalStrength] = {
    SecuritySignalType.DUPLICATE_ENTRY.value: SignalStrength.MODERATE,
    SecuritySignalType.UNUSUAL_ENTRY_POINT.value: SignalStrength.WEAK,
    SecuritySignalType.UNUSUAL_TIME.value: SignalStrength.WEAK,
    SecuritySignalType.SEAT_MISMATCH.value: SignalStrength.STRONG,
    SecuritySignalType.MULTIPLE_REGISTRATIONS.value: SignalStrength.STRONG,
    SecuritySignalType.RAPID_ENTRY.value: SignalStrength.MODERATE,
    SecuritySignalType.DOCUMENT_ANOMALY.value: SignalStrength.STRONG,
    SecuritySignalType.BEHAVIORAL_ANOMALY.value: SignalStrength.MODERATE,
    SecuritySignalType.IDENTITY_MISMATCH.value: SignalStrength.STRONG,
    SecuritySignalType.MANUAL_FLAG.value: SignalStrength.MODERATE,
}


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecuritySignal(Base):
    __tablename__ = "security_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_verification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_verifications.id"),
        nullable=False,
        index=True,
        comment="Entry verification this signal was detected for",
    )
    signal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of security signal detected",
    )
    strength: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Strength of this signal",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source that produced this signal (e.g. hall_ticket_check, identity_check, manual)",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of what was detected",
    )
    evidence_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded structured evidence data",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this signal was detected",
    )

    entry_verification: Mapped["EntryVerification"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SecuritySignal id={self.id} "
            f"entry_verification_id={self.entry_verification_id} "
            f"signal_type={self.signal_type!r} "
            f"strength={self.strength!r}>"
        )


class ProxyRiskAssessment(Base):
    __tablename__ = "proxy_risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_verification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_verifications.id"),
        nullable=False,
        index=True,
        comment="Entry verification this assessment is for",
    )
    risk_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Classified risk level",
    )
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Numeric risk score (0.0 - max_score)",
    )
    signals_summary_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON summary of signals used in this assessment",
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this assessment was performed",
    )
    policy_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Version of risk scoring policy used",
    )

    entry_verification: Mapped["EntryVerification"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ProxyRiskAssessment id={self.id} "
            f"entry_verification_id={self.entry_verification_id} "
            f"risk_level={self.risk_level!r} "
            f"risk_score={self.risk_score}>"
        )

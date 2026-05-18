"""Treatment model: one tindakan + biaya for a visit."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.visit import PatientVisit


class Treatment(Base, TimestampMixin):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("patient_visits.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    nama_tindakan: Mapped[str] = mapped_column(String(255), nullable=False)
    biaya: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False,
    )

    visit: Mapped["PatientVisit"] = relationship("PatientVisit", back_populates="treatments")

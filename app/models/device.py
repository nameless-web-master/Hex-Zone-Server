"""Device model."""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Device(Base):
    """Device model."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    hid = Column(String(255), unique=True, nullable=False, index=True)  # Hardware ID
    name = Column(String(255), nullable=False)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    h3_cell_id = Column(String(50), nullable=True, index=True)
    
    # Owner reference
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Propagation settings
    propagate_enabled = Column(Boolean, default=True, nullable=False)
    propagate_radius_km = Column(Float, default=1.0, nullable=False)
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("Owner", back_populates="devices")

    __table_args__ = (
        Index("ix_device_hid", "hid"),
        Index("ix_device_owner_id", "owner_id"),
        Index("ix_device_h3_cell", "h3_cell_id"),
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, hid={self.hid}, name={self.name})>"

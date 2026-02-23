from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from .base import Base

class GeneratedDesign(Base):

    __tablename__ = "generated_designs"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id")) 

    

    prompt_used = Column(Text)

    image_url = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    

    is_approved = Column(Boolean, default=False)

    

    product = relationship("Product", back_populates="designs")
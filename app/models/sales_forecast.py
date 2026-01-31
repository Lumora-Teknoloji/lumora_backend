from sqlalchemy import Column, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base

class SalesForecast(Base):

    __tablename__ = "sales_forecasts"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"))

    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    

    forecast_date = Column(DateTime)

    predicted_sales = Column(Integer)

    confidence_lower = Column(Integer)

    confidence_upper = Column(Integer)

    

    product = relationship("Product", back_populates="forecasts")




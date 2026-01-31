from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from .base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"))
    
    # Ürün Kimlikleri
    product_code = Column(String, index=True) # SKU veya Platform ID
    name = Column(String)
    brand = Column(String, index=True)
    
    # AI Görsel/Metin Vektörü (Arama ve Benzerlik için)
    # pgvector: CREATE EXTENSION vector; yapmayı unutma.
    feature_vector = Column(Vector(1536)) 
    
    # Teknik Özellikler
    attributes = Column(JSONB) # {renk: kırmızı, kumaş: pamuk...}
    
    task = relationship("ScrapingTask", back_populates="products")
    daily_metrics = relationship("DailyMetric", back_populates="product")
    designs = relationship("GeneratedDesign", back_populates="product")
    forecasts = relationship("SalesForecast", back_populates="product")
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB 
from .database import Base

# --- 1. KULLANICI & SOHBET ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # İlişkiler
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    
    # EKSİK OLAN KISIM EKLENDİ:
    tasks = relationship("ScrapingTask", back_populates="created_by") 


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    alias = Column(String(255))
    
    # Sohbet geçmişini JSON olarak sakla (Hızlı okuma için cache)
    history_json = Column(JSON, nullable=True, default=list)  
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender = Column(String(20), nullable=False)  # "user" | "ai"
    content = Column(Text)
    image_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


# --- 2. GÖREV YÖNETİMİ & LOGLAR ---

class ScrapingTask(Base):
    __tablename__ = "scraping_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Görev tipleri
    task_type = Column(String, default="PRODUCT_URL", nullable=False)
    search_term = Column(String, nullable=True)
    target_url = Column(String, unique=True, nullable=False)

    # Durum Takibi
    status = Column(String, nullable=False, default="pending")

    is_active = Column(Boolean, default=True)
    
    # DÜZELTME: String -> Integer yapıldı. Saat cinsinden tutulmalı.
    scrape_frequency = Column(Integer, default=24) 
    
    last_scraped_at = Column(DateTime(timezone=True))

    products = relationship("Product", back_populates="task")
    created_by = relationship("User", back_populates="tasks")
    logs = relationship("SystemLog", back_populates="task")


class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"))
    level = Column(String) # "INFO", "ERROR", "WARNING"
    message = Column(Text) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    task = relationship("ScrapingTask", back_populates="logs")


# --- 3. ÜRÜN & ÖZELLİKLER ---

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"))
    
    category_tag = Column(String, index=True) 
    product_code = Column(String, index=True) 
    name = Column(String)
    image_url = Column(String)
    url = Column(String) 
    seller_name = Column(String)
    origin = Column(String)
    
    # Fiziksel Özellikler
    size = Column(String)        
    color = Column(String)
    fabric_type = Column(String)
    pattern = Column(String)
    neck_style = Column(String)
    sleeve_type = Column(String)
    length = Column(String)
    
    # AI Analizi İçin Metin Alanı
    description_vector = Column(Text) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    task = relationship("ScrapingTask", back_populates="products")
    daily_metrics = relationship("DailyMetric", back_populates="product")
    forecasts = relationship("SalesForecast", back_populates="product")
    designs = relationship("GeneratedDesign", back_populates="product")


# --- 4. ZAMAN SERİSİ VERİLERİ ---

class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    price = Column(Float)
    discounted_price = Column(Float)
    
    # Stok Durumu
    in_stock = Column(Boolean, default=True) 
    available_sizes = Column(String) 
    
    cart_count = Column(Integer)     
    favorite_count = Column(Integer) 
    clicks_24h = Column(Integer)     
    
    review_count = Column(Integer)
    rating = Column(Float)
    qa_count = Column(Integer) 
    
    review_summary = Column(Text) 
    
    calculated_daily_sales = Column(Integer) 
    momentum_score = Column(Float)           
    
    product = relationship("Product", back_populates="daily_metrics")


# --- 5. TAHMİN & TASARIM ---

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

class GeneratedDesign(Base):
    __tablename__ = "generated_designs"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id")) 
    
    prompt_used = Column(Text)
    image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    is_approved = Column(Boolean, default=False)
    
    product = relationship("Product", back_populates="designs")
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from .base import Base


class ProductCollection(Base):
    """
    Kullanıcının oluşturduğu ürün koleksiyonları.
    YouTube oynatma listesi benzeri — ürünleri kategorize etmek için.
    """
    __tablename__ = "product_collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    color = Column(String(7), default="#4cc9f0")  # Hex renk kodu
    icon = Column(String(50), default="folder")   # Lucide ikon adı
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # İlişkiler
    items = relationship("ProductCollectionItem", back_populates="collection", cascade="all, delete-orphan")
    user = relationship("User")


class ProductCollectionItem(Base):
    """Bir koleksiyondaki ürün."""
    __tablename__ = "product_collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("product_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("collection_id", "product_id", name="uq_collection_product"),
    )

    collection = relationship("ProductCollection", back_populates="items")
    product = relationship("Product")


class ProductReaction(Base):
    """
    Kullanıcının ürüne verdiği beğen/beğenme reaksiyonu.
    Instagram tarzı — her kullanıcı her ürüne tek reaksiyon verebilir.
    """
    __tablename__ = "product_reactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction = Column(String(10), nullable=False)  # "like" veya "dislike"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_reaction"),
    )

    user = relationship("User")
    product = relationship("Product")

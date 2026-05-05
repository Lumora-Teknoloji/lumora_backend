import pytest
from app.models.product import Product
from app.models.daily_metric import DailyMetric
from unittest.mock import MagicMock
from datetime import datetime, timezone

def test_list_products_empty(client, db_session):
    db_session.query.return_value.count.return_value = 0
    db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    
    response = client.get("/api/products")

def test_list_products_with_data(client, db_session):
    p = Product(id=1, name="Test Shirt", brand="TestBrand", last_price=100.0)
    
    # Mock total count
    db_session.query.return_value.count.return_value = 1
    # Mock pagination return
    db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [p]
    # Mock daily metric fetch
    db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Test Shirt"
    assert data["items"][0]["brand"] == "TestBrand"

def test_get_product_not_found(client, db_session):
    db_session.query.return_value.filter.return_value.first.return_value = None
    response = client.get("/api/products/9999")

def test_get_product_success(client, db_session):
    p = Product(id=1, name="Single Product", last_price=200.0)
    # Return the product, then return None for the daily metric
    db_session.query.return_value.filter.return_value.first.side_effect = [p, None]
    # Handle the .order_by().first() for metric
    db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    response = client.get(f"/api/products/{p.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Single Product"

def test_data_quality(client, db_session):
    mock_result = MagicMock()
    mock_result.fetchone.side_effect = [
        (10, 8, 8, 8, 8, 8), # main query
        (5, 5, 5)            # metrics query
    ]
    db_session.execute.return_value = mock_result
    
    response = client.get("/api/products/quality")
    data = response.json()
    assert "total_products" in data
    assert "seller_filled" in data

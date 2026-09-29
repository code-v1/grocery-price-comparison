import pytest
from fastapi.testclient import TestClient
from grocery_price_agent import app, PriceQuote, PriceQuoteRequest

client = TestClient(app)

def test_single_store_mode():
    response = client.post(
        "/quote",
        json={
            "items": ["2% milk", "eggs 12ct", "cheddar 8oz"],
            "budget": 60.0,
            "zip": "27601",
            "mode": "single"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_price" in data
    assert "savings" in data
    assert "store" in data
    assert "items" in data
    assert len(data["items"]) == 3

def test_split_store_mode():
    response = client.post(
        "/quote",
        json={
            "items": ["2% milk", "eggs 12ct", "cheddar 8oz"],
            "budget": 60.0,
            "zip": "27601",
            "mode": "split"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_price" in data
    assert "savings" in data
    assert "store" in data
    assert "items" in data
    assert len(data["items"]) == 3

def test_invalid_item():
    response = client.post(
        "/quote",
        json={
            "items": ["invalid item"],
            "budget": 60.0,
            "zip": "27601",
            "mode": "single"
        }
    )
    assert response.status_code == 200  # Should still work with demo data
    data = response.json()
    assert "total_price" in data
    assert "savings" in data

def test_budget_constraint():
    response = client.post(
        "/quote",
        json={
            "items": ["2% milk", "eggs 12ct", "cheddar 8oz"],
            "budget": 10.0,  # Very low budget
            "zip": "27601",
            "mode": "single"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_price"] > 0
    assert data["savings"] < 0  # Should be negative since budget is too low

def test_empty_items():
    response = client.post(
        "/quote",
        json={
            "items": [],
            "budget": 60.0,
            "zip": "27601",
            "mode": "single"
        }
    )
    assert response.status_code == 400
    assert "No items provided" in response.json()["detail"]

def test_negative_budget():
    response = client.post(
        "/quote",
        json={
            "items": ["2% milk"],
            "budget": -10.0,
            "zip": "27601",
            "mode": "single"
        }
    )
    assert response.status_code == 400
    assert "Budget must be positive" in response.json()["detail"] 
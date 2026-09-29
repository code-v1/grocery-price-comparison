# GroceryGetter — Price Comparison API

A Python API prototype exploring how a shopping list and budget can be compared across grocery stores. It uses deterministic demo store prices to make the comparison flow easy to inspect.

## What it does

- Typed shopping-list requests and price-quote responses.
- Asynchronous collection of store quotes.
- Core comparison logic for a single-store basket or a split-store basket.
- Budget-relative savings calculation in the comparison layer.
- FastAPI route, API documentation, and test files.

## Built with

Python · FastAPI · Pydantic · HTTPX · asyncio

## Example

Example request shape for the `/quote` endpoint:

```json
{"items": ["milk", "bread"], "budget": 20, "zip": "75034", "mode": "single"}
```

Store prices in this prototype are demo values.

## Run locally

Install dependencies with `pip install -r requirements.txt`, then run `uvicorn grocery_price_agent:app --reload`. Open `http://127.0.0.1:8000/docs` to explore the API schema.

## Code guide

`grocery_price_agent.py` contains request models, demo price providers, comparison logic, and the `/quote` endpoint. `test_grocery_price_agent.py` contains tests.

# grocery_price_agent.py
from __future__ import annotations

import asyncio
import os
import sys
import types
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Ensure `ssl` imports never explode in stripped‑down environments
# ---------------------------------------------------------------------------
try:
    import ssl as _ssl  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – sandbox without OpenSSL
    _ssl = types.ModuleType("ssl")
    _ssl.SSLContext = object  # type: ignore[attr-defined]
    sys.modules["ssl"] = _ssl

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError
import httpx
from dotenv import load_dotenv
import random

load_dotenv()

app = FastAPI(title="Grocery Price Comparison API")

# API configurations
KROGER_BASE_URL = "https://api.kroger.com/v1"
WALMART_BASE_URL = "https://api.walmart.com/v3"
KROGER_CLIENT_ID = os.getenv("KROGER_CLIENT_ID", "demo")
KROGER_CLIENT_SECRET = os.getenv("KROGER_CLIENT_SECRET", "demo")
WALMART_API_KEY = os.getenv("WALMART_API_KEY", "demo")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class PriceQuoteRequest(BaseModel):
    items: List[str]
    budget: float
    zip: str
    mode: str = "single"

class PriceQuote(BaseModel):
    total_price: float
    savings: float
    store: str
    items: Dict[str, float]

# ---------------------------------------------------------------------------
# Stubbed price fetchers (replace with real API calls later)
# ---------------------------------------------------------------------------
async def fetch_kroger_price(_: Optional[httpx.AsyncClient], item: str, __: str) -> Dict[str, float]:
    await asyncio.sleep(0)  # keep function truly async
    return {item: 3.49}


async def fetch_walmart_price(_: Optional[httpx.AsyncClient], item: str, __: str) -> Dict[str, float]:
    await asyncio.sleep(0)
    return {item: 3.29}


CHAIN_FETCHERS = {
    "kroger": fetch_kroger_price,
    "walmart": fetch_walmart_price,
}

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
async def _gather_prices(req: PriceQuoteRequest, session: Optional[httpx.AsyncClient]):
    tasks = {
        chain: [asyncio.create_task(fetcher(session, itm, req.zip)) for itm in req.items]
        for chain, fetcher in CHAIN_FETCHERS.items()
    }
    return {c: await asyncio.gather(*t) for c, t in tasks.items()}


async def price_runner(req: PriceQuoteRequest) -> List[PriceQuote]:
    if HTTPX_AVAILABLE:
        async with httpx.AsyncClient(timeout=10) as client:
            chain_results = await _gather_prices(req, client)
    else:
        chain_results = await _gather_prices(req, None)

    quotes: List[PriceQuote] = []
    for chain, results in chain_results.items():
        subtotal = sum(price for d in results for price in d.values())
        quotes.append(
            PriceQuote(
                store=chain,
                total_price=round(subtotal, 2),
                items={k: v for d in results for k, v in d.items()},
                savings=round(req.budget - subtotal, 2),
            )
        )

    if req.mode == "single":
        return [min(quotes, key=lambda q: q.total_price)]

    cheapest_split: Dict[str, Dict[str, float]] = {}
    for item in req.items:
        best_price, best_store = float("inf"), ""
        for quote in quotes:
            price = quote.items.get(item, float("inf"))
            if price < best_price:
                best_price, best_store = price, quote.store
        cheapest_split.setdefault(best_store, {})[item] = best_price

    return [
        PriceQuote(
            store=s,
            items=itm,
            total_price=round(sum(itm.values()), 2),
            savings=round(req.budget - sum(itm.values()), 2),
        )
        for s, itm in cheapest_split.items()
    ]


# ---------------------------------------------------------------------------
# FastAPI route
# ---------------------------------------------------------------------------
@app.post("/quote", response_model=PriceQuote)
async def get_price_quote(request: PriceQuoteRequest):
    """Get price quote for grocery items."""
    if not request.items:
        raise HTTPException(status_code=400, detail="No items provided")
        
    if request.budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be positive")
        
    prices = await price_runner(request)
    
    if request.mode == "single":
        # Find best single store
        store_totals = {
            "kroger": sum(prices[0].items.get("kroger", 0) for item in request.items),
            "walmart": sum(prices[0].items.get("walmart", 0) for item in request.items)
        }
        best_store = min(store_totals.items(), key=lambda x: x[1])[0]
        total_price = store_totals[best_store]
        item_prices = {item: prices[0].items.get(item, 0) for item in request.items}
        
    else:  # split mode
        # Find best combination of stores
        total_price = 0
        item_prices = {}
        store_assignments = {}
        
        for item in request.items:
            if prices[0].items.get("kroger", 0) <= prices[0].items.get("walmart", 0):
                store = "kroger"
                price = prices[0].items.get("kroger", 0)
            else:
                store = "walmart"
                price = prices[0].items.get("walmart", 0)
                
            total_price += price
            item_prices[item] = price
            store_assignments[item] = store
            
        # If total exceeds budget, try to optimize
        if total_price > request.budget:
            # Sort items by price difference between stores
            items_by_diff = sorted(
                request.items,
                key=lambda x: abs(prices[0].items.get("kroger", 0) - prices[0].items.get("walmart", 0)),
                reverse=True
            )
            
            # Try to switch stores for items with biggest price differences
            for item in items_by_diff:
                current_store = store_assignments[item]
                other_store = "walmart" if current_store == "kroger" else "kroger"
                
                if prices[0].items.get(other_store, 0) < prices[0].items.get(current_store, 0):
                    price_diff = prices[0].items.get(current_store, 0) - prices[0].items.get(other_store, 0)
                    if total_price - price_diff <= request.budget:
                        total_price -= price_diff
                        item_prices[item] = prices[0].items.get(other_store, 0)
                        store_assignments[item] = other_store
                        
        best_store = " & ".join(sorted(set(store_assignments.values())))
        
    savings = request.budget - total_price
    
    return PriceQuote(
        total_price=round(total_price, 2),
        savings=round(savings, 2),
        store=best_store,
        items=item_prices
    )

# ---------------------------------------------------------------------------
# Self‑tests
# ---------------------------------------------------------------------------
async def _selftest():
    # happy‑path single mode
    r1 = PriceQuoteRequest(items=["2% milk", "eggs 12ct"], budget=10, zip="27601")
    q1 = await price_runner(r1)
    assert q1 and q1[0].total_price == 6.58

    # happy‑path split mode
    r1.mode = "split"
    q2 = await price_runner(r1)
    assert sum(x.total_price for x in q2) == 6.58

    # low budget → negative savings
    low = PriceQuoteRequest(items=["2% milk"], budget=1, zip="27601")
    q_low = await price_runner(low)
    assert q_low[0].savings == -2.29

    # invalid mode triggers validation error
    try:
        PriceQuoteRequest(items=["water"], budget=5, zip="27601", mode="invalid")
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid mode accepted")

    print("✅  All self‑tests passed.")


def _run_async(coro):
    """Run *coro* regardless of whether an event loop is already running."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # no loop → safe to use asyncio.run
        asyncio.run(coro)
    else:  # loop already running (e.g. Jupyter) – schedule task and wait
        task = loop.create_task(coro)
        # Jupyter notebooks usually keep the loop alive; waiting with gather
        # makes the call blocking in scripts yet non‑blocking in notebooks.
        loop.run_until_complete(asyncio.gather(task))


if __name__ == "__main__":
    _run_async(_selftest())

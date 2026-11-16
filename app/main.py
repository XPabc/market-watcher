import os
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import alerts, db, market

INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
DEFAULT_COINS = os.environ.get("COINS", "bitcoin,ethereum,solana").split(",")


def poll_forever(stop_event):
    while not stop_event.is_set():
        try:
            # Watch the default coins plus any coin that has an alert.
            coins = sorted(set(DEFAULT_COINS) | {a["coin"] for a in db.list_alerts()})
            fetched = market.get_prices(coins)
            db.save_prices(fetched)
            alerts.check_alerts(fetched)
        except Exception as error:
            # A background thread that dies silently is worse than a noisy one,
            # so we log the problem and keep going.
            print(f"Poll failed: {error}")
        # Like time.sleep(), but wakes up immediately when asked to stop.
        stop_event.wait(INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    stop_event = threading.Event()
    thread = threading.Thread(target=poll_forever, args=(stop_event,), daemon=True)
    thread.start()
    yield
    stop_event.set()
    thread.join(timeout=5)


app = FastAPI(title="Market Watcher", lifespan=lifespan)


class AlertIn(BaseModel):
    coin: str = Field(min_length=1)
    direction: Literal["above", "below"]
    price: float = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/prices")
def latest_prices():
    return db.latest_prices()


@app.get("/alerts")
def list_alerts():
    return db.list_alerts()


@app.post("/alerts", status_code=201)
def create_alert(alert: AlertIn):
    alert_id = db.add_alert(alert.coin.lower(), alert.direction, alert.price)
    return {"id": alert_id}


@app.delete("/alerts/{alert_id}", status_code=204)
def remove_alert(alert_id: int):
    if not db.delete_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")

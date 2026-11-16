import os

import requests

from app import db


def is_crossed(price, direction, threshold):
    if direction == "below":
        return price < threshold
    return price > threshold


def send_discord(message):
    """Return True if the message was sent, False otherwise."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print(f"[DISCORD_WEBHOOK_URL not set] {message}")
        return False
    try:
        response = requests.post(webhook_url, json={"content": message}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"Could not send Discord message: {error}")
        return False


def check_alerts(prices):
    for alert in db.list_alerts():
        price = prices.get(alert["coin"])
        if price is None:
            continue
        crossed = is_crossed(price, alert["direction"], alert["price"])
        if crossed and not alert["triggered"]:
            message = (
                f"ALERT: {alert['coin'].capitalize()} is {alert['direction']} "
                f"${alert['price']:,.2f} (now ${price:,.2f})"
            )
            # Only mark it as fired if Discord accepted it,
            # otherwise we retry on the next cycle.
            if send_discord(message):
                db.set_triggered(alert["id"], True)
        elif not crossed and alert["triggered"]:
            # Price is back on the normal side: re-arm the alert.
            db.set_triggered(alert["id"], False)

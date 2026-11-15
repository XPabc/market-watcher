import os
import time

import requests

URL = "https://api.coingecko.com/api/v3/simple/price"
COINS = ["bitcoin", "ethereum", "solana"]
CURRENCY = "usd"
INTERVAL_SECONDS = 60

# The webhook URL is a secret, so it comes from the environment, not the code.
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Edit these. "direction" is "above" or "below".
ALERTS = [
    {"coin": "bitcoin", "direction": "below", "price": 65500},
    {"coin": "ethereum", "direction": "above", "price": 5000},
]


def get_prices(coin_ids, currency="usd"):
    response = requests.get(
        URL,
        params={"ids": ",".join(coin_ids), "vs_currencies": currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return {coin: data[coin][currency] for coin in coin_ids if coin in data}


def send_discord(message):
    """Return True if the message was sent, False otherwise."""
    if not WEBHOOK_URL:
        print(f"[DISCORD_WEBHOOK_URL not set] {message}")
        return False
    try:
        response = requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"Could not send Discord message: {error}")
        return False


def is_crossed(price, alert):
    if alert["direction"] == "below":
        return price < alert["price"]
    return price > alert["price"]


def check_alerts(prices, triggered):
    for index, alert in enumerate(ALERTS):
        price = prices.get(alert["coin"])
        if price is None:
            continue
        if is_crossed(price, alert):
            if index not in triggered:
                message = (
                    f"ALERT: {alert['coin'].capitalize()} is {alert['direction']} "
                    f"${alert['price']:,.2f} (now ${price:,.2f})"
                )
                if send_discord(message):
                    triggered.add(index)
        else:
            # Price is back on the normal side, so re-arm the alert.
            triggered.discard(index)


def main():
    triggered = set()
    while True:
        try:
            prices = get_prices(COINS, CURRENCY)
            for coin, price in prices.items():
                print(f"{coin.capitalize()}: ${price:,.2f}")
            check_alerts(prices, triggered)
        except requests.RequestException as error:
            print(f"Could not fetch prices: {error}")
        print("---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.")

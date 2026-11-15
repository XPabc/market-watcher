import requests

URL = "https://api.coingecko.com/api/v3/simple/price"


def get_price(coin_id, currency="usd"):
    response = requests.get(
        URL,
        params={"ids": coin_id, "vs_currencies": currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data[coin_id][currency]


if __name__ == "__main__":
    price = get_price("bitcoin")
    print(f"Bitcoin: ${price:,.2f}")

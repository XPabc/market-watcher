import requests

URL = "https://api.coingecko.com/api/v3/simple/price"


def get_prices(coin_ids, currency="usd"):
    response = requests.get(
        URL,
        params={"ids": ",".join(coin_ids), "vs_currencies": currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return {coin: data[coin][currency] for coin in coin_ids if coin in data}

"""
Test Bitquery OHLCV data fetching with proper token pairs
"""
import os
import requests
from datetime import datetime, UTC, timedelta

# Get credentials
client_id = os.getenv("BITQUERY_CLIENT_ID")
client_secret = os.getenv("BITQUERY_CLIENT_SECRET")

# Get access token
token_url = "https://oauth2.bitquery.io/oauth2/token"
payload = {
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": "api",
}
headers = {"Content-Type": "application/x-www-form-urlencoded"}
resp = requests.post(token_url, data=payload, headers=headers, timeout=30)
resp.raise_for_status()
token_data = resp.json()
access_token = token_data.get("access_token")
print(f"[OK] Got access token")

# Let's first find an actual meme token
print("\nFinding recent meme tokens...")
since_dt = datetime.now(UTC) - timedelta(days=3)

find_query = f"""
query {{
  Solana {{
    DEXTradeByTokens(
      limit: {{count: 50}}
      orderBy: {{descending: Block_Time}}
      where: {{
        Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z"}}}}
        Trade: {{
          Side: {{Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}}}
        }}
      }}
    ) {{
      Trade {{
        Currency {{
          Symbol
          MintAddress
          Name
        }}
        Side {{
          Currency {{
            Symbol
            MintAddress
          }}
        }}
        PriceInUSD
        PriceAgainstSideCurrency
      }}
    }}
  }}
}}
"""

url = "https://streaming.bitquery.io/graphql"
headers_req = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}",
}

response = requests.post(url, json={"query": find_query}, headers=headers_req, timeout=30)
data = response.json()

if data.get("errors"):
    print("Errors:", data["errors"])
    exit(1)

trades = data.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
print(f"Found {len(trades)} trades")

# Pick a token with good data
token_info = None
for trade in trades:
    currency = trade.get("Trade", {}).get("Currency", {})
    side = trade.get("Trade", {}).get("Side", {}).get("Currency", {})
    price_usd = trade.get("Trade", {}).get("PriceInUSD")
    price_sol = trade.get("Trade", {}).get("PriceAgainstSideCurrency")
    
    if currency.get("Symbol") and side.get("Symbol") == "WSOL" and price_sol and float(price_sol) > 0:
        token_info = {
            "symbol": currency.get("Symbol"),
            "mint": currency.get("MintAddress"),
            "name": currency.get("Name"),
            "price_sol": price_sol
        }
        print(f"\nFound token: {token_info['symbol']} ({token_info['name']})")
        print(f"  Mint: {token_info['mint']}")
        print(f"  Price: {token_info['price_sol']} SOL")
        break

if not token_info:
    print("Could not find a suitable meme token")
    exit(1)

# Now fetch OHLC data for this token
print(f"\nFetching OHLC data for {token_info['symbol']}/SOL...")

ohlc_query = f"""
query {{
  Solana {{
    DEXTradeByTokens(
      limit: {{count: 500}}
      orderBy: {{ascending: Block_Time}}
      where: {{
        Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z"}}}}
        Trade: {{
          Currency: {{MintAddress: {{is: "{token_info['mint']}"}}}}
          Side: {{Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}}}
        }}
      }}
    ) {{
      Block {{
        timeBucket: Time(interval: {{in: hours, count: 1}})
      }}
      Trade {{
        open: PriceAgainstSideCurrency(minimum: Block_Time)
        high: PriceAgainstSideCurrency(maximum: Block_Slot)
        low: PriceAgainstSideCurrency(minimum: Block_Slot)
        close: PriceAgainstSideCurrency(maximum: Block_Time)
        volume: Amount(maximum: Block_Slot)
      }}
    }}
  }}
}}
"""

response = requests.post(url, json={"query": ohlc_query}, headers=headers_req, timeout=30)
data = response.json()

if data.get("errors"):
    print("Errors:", data["errors"])
else:
    candles = data.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
    print(f"[OK] Got {len(candles)} OHLC candles")
    
    if candles:
        print("\nFirst 5 candles:")
        for i, candle in enumerate(candles[:5]):
            block = candle.get('Block', {})
            trade = candle.get('Trade', {})
            print(f"\n  Candle {i+1}:")
            print(f"    Time: {block.get('timeBucket')}")
            print(f"    Open: {trade.get('open')}")
            print(f"    High: {trade.get('high')}")
            print(f"    Low: {trade.get('low')}")
            print(f"    Close: {trade.get('close')}")
            print(f"    Volume: {trade.get('volume')}")
            
            # Check if we have valid prices
            if float(trade.get('close', 0) or 0) > 0:
                print(f"    [OK] Valid price data!")


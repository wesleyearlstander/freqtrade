"""
Test Bitquery OHLCV data fetching
"""
import os
import requests
from datetime import datetime, UTC, timedelta

# Get credentials
client_id = os.getenv("BITQUERY_CLIENT_ID")
client_secret = os.getenv("BITQUERY_CLIENT_SECRET")

if not client_id or not client_secret:
    print("Error: BITQUERY_CLIENT_ID and BITQUERY_CLIENT_SECRET must be set")
    exit(1)

print("Step 1: Getting access token...")
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
print(f"[OK] Got access token (expires in {token_data.get('expires_in')} seconds)")

# Test OHLCV query
print("\nStep 2: Testing OHLCV query...")
since_dt = datetime.now(UTC) - timedelta(days=7)
until_dt = datetime.now(UTC)

# Simpler query to test
query = f"""
query {{
  Solana {{
    DEXTradeByTokens(
      limit: {{count: 100}}
      orderBy: {{descending: Block_Time}}
      where: {{
        Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z"}}}}
        Trade: {{
          Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}
          Side: {{Currency: {{MintAddress: {{notIn: ["So11111111111111111111111111111111111111112"]}}}}}}
        }}
      }}
    ) {{
      Block {{
        Time
      }}
      Trade {{
        Currency {{
          Symbol
          MintAddress
        }}
        Side {{
          Currency {{
            Symbol
            MintAddress
          }}
        }}
        PriceInUSD
        Amount
      }}
    }}
  }}
}}
"""

url = "https://streaming.bitquery.io/graphql"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}",
}

print("Sending query to Bitquery...")
response = requests.post(url, json={"query": query}, headers=headers, timeout=30)
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data.get("errors"):
        print("GraphQL Errors:")
        for error in data["errors"]:
            print(f"  - {error.get('message', error)}")
    else:
        trades = data.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
        print(f"[OK] Got {len(trades)} trades")
        if trades:
            print("\nFirst trade sample:")
            trade = trades[0]
            print(f"  Time: {trade.get('Block', {}).get('Time')}")
            print(f"  Base: {trade.get('Trade', {}).get('Currency', {}).get('Symbol')}")
            print(f"  Quote: {trade.get('Trade', {}).get('Side', {}).get('Currency', {}).get('Symbol')}")
            print(f"  Price: {trade.get('Trade', {}).get('PriceInUSD')}")
            print(f"  Amount: {trade.get('Trade', {}).get('Amount')}")
else:
    print(f"Error: {response.text}")

# Now test OHLC aggregation query
print("\n\nStep 3: Testing OHLC aggregation query...")

ohlc_query = f"""
query {{
  Solana {{
    DEXTradeByTokens(
      limit: {{count: 1000}}
      orderBy: {{ascending: Block_Time}}
      where: {{
        Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z"}}}}
        Trade: {{
          Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}
          Side: {{Currency: {{MintAddress: {{notIn: ["So11111111111111111111111111111111111111112"]}}}}}}
        }}
      }}
    ) {{
      Block {{
        timeBucket: Time(interval: {{in: minutes, count: 60}})
      }}
      Trade {{
        high: PriceInUSD(maximum: Block_Slot)
        low: PriceInUSD(minimum: Block_Slot)
        open: PriceInUSD(minimum: Block_Time)
        close: PriceInUSD(maximum: Block_Time)
        volume: Amount(maximum: Block_Slot)
      }}
    }}
  }}
}}
"""

response = requests.post(url, json={"query": ohlc_query}, headers=headers, timeout=30)
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data.get("errors"):
        print("GraphQL Errors:")
        for error in data["errors"]:
            print(f"  - {error.get('message', error)}")
    else:
        candles = data.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
        print(f"[OK] Got {len(candles)} OHLC candles")
        if candles:
            print("\nFirst 3 candles:")
            for i, candle in enumerate(candles[:3]):
                block = candle.get('Block', {})
                trade = candle.get('Trade', {})
                print(f"\n  Candle {i+1}:")
                print(f"    Time: {block.get('timeBucket')}")
                print(f"    Open: {trade.get('open')}")
                print(f"    High: {trade.get('high')}")
                print(f"    Low: {trade.get('low')}")
                print(f"    Close: {trade.get('close')}")
                print(f"    Volume: {trade.get('volume')}")
else:
    print(f"Error: {response.text}")


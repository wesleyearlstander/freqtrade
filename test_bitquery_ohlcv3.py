"""
Test Bitquery raw trades and manual OHLC calculation
"""
import os
import requests
import pandas as pd
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

# Let's query raw trades and see what fields are available
print("\nQuerying raw trades...")
since_dt = datetime.now(UTC) - timedelta(days=2)

raw_query = f"""
query {{
  Solana {{
    DEXTradeByTokens(
      limit: {{count: 100}}
      orderBy: {{descending: Block_Time}}
      where: {{
        Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z"}}}}
        Trade: {{
          Side: {{Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}}}
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
          Amount
        }}
        Amount
        Price
        PriceInUSD
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

response = requests.post(url, json={"query": raw_query}, headers=headers_req, timeout=30)
data = response.json()

if data.get("errors"):
    print("Errors:", data["errors"])
    exit(1)

trades = data.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
print(f"Found {len(trades)} trades")

if trades:
    print("\nFirst trade details:")
    trade = trades[0]
    print(f"  Time: {trade.get('Block', {}).get('Time')}")
    print(f"  Base Token: {trade.get('Trade', {}).get('Currency', {}).get('Symbol')}")
    print(f"  Quote Token: {trade.get('Trade', {}).get('Side', {}).get('Currency', {}).get('Symbol')}")
    print(f"  Amount: {trade.get('Trade', {}).get('Amount')}")
    print(f"  Side Amount (SOL): {trade.get('Trade', {}).get('Side', {}).get('Amount')}")
    print(f"  Price: {trade.get('Trade', {}).get('Price')}")
    print(f"  PriceInUSD: {trade.get('Trade', {}).get('PriceInUSD')}")
    
    # Calculate price in SOL
    amount = float(trade.get('Trade', {}).get('Amount') or 0)
    side_amount = float(trade.get('Trade', {}).get('Side', {}).get('Amount') or 0)
    if amount > 0:
        price_in_sol = side_amount / amount
        print(f"  Calculated Price in SOL: {price_in_sol}")
    
    # Pick a token and aggregate trades into OHLC
    token_mint = trade.get('Trade', {}).get('Currency', {}).get('MintAddress')
    token_symbol = trade.get('Trade', {}).get('Currency', {}).get('Symbol')
    
    print(f"\nAggregating trades for {token_symbol} into OHLC...")
    
    # Convert trades to DataFrame
    rows = []
    for t in trades:
        if t.get('Trade', {}).get('Currency', {}).get('MintAddress') == token_mint:
            amount = float(t.get('Trade', {}).get('Amount') or 0)
            side_amount = float(t.get('Trade', {}).get('Side', {}).get('Amount') or 0)
            
            if amount > 0 and side_amount > 0:
                price_in_sol = side_amount / amount
                rows.append({
                    'time': t.get('Block', {}).get('Time'),
                    'price': price_in_sol,
                    'amount': amount
                })
    
    if rows:
        df = pd.DataFrame(rows)
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')
        
        # Resample to 1H candles
        ohlc = df['price'].resample('1H').ohlc()
        volume = df['amount'].resample('1H').sum()
        
        print(f"\nOHLC Candles for {token_symbol}:")
        print(ohlc.head(10))
        print(f"\nFirst candle with data:")
        for idx, row in ohlc.iterrows():
            if pd.notna(row['close']) and row['close'] > 0:
                print(f"  Time: {idx}")
                print(f"  Open: {row['open']:.10f} SOL")
                print(f"  High: {row['high']:.10f} SOL")
                print(f"  Low: {row['low']:.10f} SOL")
                print(f"  Close: {row['close']:.10f} SOL")
                print(f"  Volume: {volume.loc[idx]:.6f}")
                break
    else:
        print("No valid trades found for this token")


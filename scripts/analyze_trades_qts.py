import glob
import io
import os
import sys
import zipfile
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# Analysis script for QuantumTactics_Synthesis backtests
# - Loads exported trades CSV
# - Loads local OHLCV data (1m and 1h)
# - Recomputes indicators to snapshot values at entry/exit
# - Prints diagnostics for worst/best trades and aggregate heuristics


def find_data_file(base_dir: str, pair_key: str, timeframe: str) -> str:
    patterns = [
        os.path.join(base_dir, f"**/*{pair_key}*{timeframe}.json*"),
        os.path.join(base_dir, f"**/*{pair_key}*{timeframe}.feather"),
    ]
    matches: list[str] = []
    for pat in patterns:
        matches.extend(glob.glob(pat, recursive=True))
    if not matches:
        raise FileNotFoundError(f"No data file found for patterns under {base_dir} for {pair_key} {timeframe}")
    # Prefer json.gz, then json, then feather
    def sort_key(p: str):
        if p.endswith('.json.gz'):
            return (0, p)
        if p.endswith('.json'):
            return (1, p)
        if p.endswith('.feather'):
            return (2, p)
        return (3, p)
    matches.sort(key=sort_key)
    return matches[0]


def load_ohlcv(path: str) -> pd.DataFrame:
    if path.endswith('.json') or path.endswith('.json.gz'):
        df = pd.read_json(path, lines=True)
    elif path.endswith('.feather'):
        df = pd.read_feather(path)
    else:
        raise ValueError(f"Unsupported OHLCV file format: {path}")
    # Normalize columns
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], utc=True)
    else:
        # freqtrade stores 'date' col; fallback if needed
        for c in ['time', 'timestamp']:
            if c in df.columns:
                df['date'] = pd.to_datetime(df[c], utc=True)
                break
    return df.sort_values('date').reset_index(drop=True)


def compute_indicators(df1m: pd.DataFrame, df1h: pd.DataFrame) -> pd.DataFrame:
    import pandas_ta as pta
    import talib as ta

    df = df1m.copy()

    if df.empty:
        return df

    # ADX
    for p in [5, 7, 10]:
        df[f'adx_{p}'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=p)

    # TEMA
    for p in [5, 8, 13]:
        df[f'tema_{p}'] = ta.TEMA(df['close'], timeperiod=p)

    # EMA 200
    df['ema_200'] = ta.EMA(df['close'], timeperiod=200)

    # OBV and MAs
    df['obv'] = ta.OBV(df['close'], df['volume'])
    for w in [20, 30, 50]:
        df[f'obv_ma_{w}'] = df['obv'].rolling(w).mean()

    # MACD
    macd, macdsig, macdhist = ta.MACD(df['close'])
    df['macd'] = macd
    df['macdsignal'] = macdsig
    df['macdhist'] = macdhist

    # RSI
    for p in [7, 10, 14]:
        df[f'rsi_{p}'] = ta.RSI(df['close'], timeperiod=p)

    # SuperTrend (compute only the primary combo to keep runtime bounded)
    if len(df) >= 100:
        try:
            _len, _mult = 13, 1.5
            st = pta.supertrend(df['high'], df['low'], df['close'], length=_len, multiplier=_mult)
            if st is not None:
                val_col = st.columns[0]
                dir_col = st.columns[1]
                df[f'supertrend_{_len}_{_mult}'] = st[val_col]
                df[f'supertrend_direction_{_len}_{_mult}'] = st[dir_col]
        except Exception:
            pass

    # ATR
    df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # Merge 1h EMA200 context
    if isinstance(df1h, pd.DataFrame) and not df1h.empty:
        dfh = df1h.copy()
        try:
            dfh['ema_200'] = ta.EMA(dfh['close'], timeperiod=200)
            dfh = dfh[['date', 'close', 'ema_200']].rename(columns={'close': 'close_1h', 'ema_200': 'ema_200_1h'})
            df = pd.merge_asof(
                df.sort_values('date'),
                dfh.sort_values('date'),
                on='date', direction='backward', tolerance=pd.Timedelta('1h')
            )
        except Exception:
            pass
    return df


def snapshot_row(df: pd.DataFrame, ts: pd.Timestamp) -> pd.Series:
    # Find candle at or immediately before timestamp
    idx = df['date'].searchsorted(ts, side='right') - 1
    if idx < 0:
        idx = 0
    return df.iloc[idx]


def load_ohlcv_via_freqtrade(pair: str, timeframe: str, candle_type: str = 'futures') -> pd.DataFrame:
    # Load candles using Freqtrade utilities similar to the example notebook
    from freqtrade.configuration import Configuration
    from freqtrade.data.history import load_pair_history
    from freqtrade.enums import CandleType

    # Prefer futures config if present, else default
    cfg_path = Path('quanttactics') / 'binance_futures_QuantumTactics_Synthesis.json'
    try:
        if cfg_path.exists():
            config = Configuration.from_files([str(cfg_path)])
        else:
            config = Configuration.from_files([])
    except Exception:
        config = Configuration.from_files([])

    datadir = Path(config.get('datadir', Path('user_data') / 'data' / 'binance'))
    ctype = CandleType.FUTURES if candle_type.lower() == 'futures' else CandleType.SPOT

    # Try json first, then feather as fallback
    df = pd.DataFrame()
    for fmt in ("json", "feather"):
        try:
            df = load_pair_history(
                datadir=datadir,
                timeframe=timeframe,
                pair=pair,
                data_format=fmt,
                candle_type=ctype,
            )
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                break
        except Exception:
            continue

    if isinstance(df, pd.DataFrame) and len(df) > 0:
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], utc=True)
        return df.sort_values('date').reset_index(drop=True)

    # Fallback to reading raw files from datadir
    base_dir = datadir / ('futures' if ctype == CandleType.FUTURES else '')
    pair_key = pair.replace('/', '_').replace(':', '-')  # e.g., BTC_USDT-USDT
    try:
        path = find_data_file(str(base_dir), pair_key, timeframe)
        return load_ohlcv(path)
    except Exception:
        return pd.DataFrame()


def load_trades_df() -> pd.DataFrame:
    # Preferred: use Freqtrade's btanalysis utilities to load the latest backtest
    try:
        from freqtrade.data.btanalysis import load_backtest_data
        bt_dir = Path('user_data') / 'backtest_results'
        if bt_dir.exists():
            trades = load_backtest_data(bt_dir)
            if isinstance(trades, pd.DataFrame) and not trades.empty:
                return trades
    except Exception:
        pass

    # Preferred: explicit CSV path if available
    csv_path = os.path.join('user_data', 'backtest_results', 'QTS_BTC_1m_Jan2024_trades.csv')
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)

    # Fallback 1: latest backtest-result-*.json (excluding meta)
    results_dir = os.path.join('user_data', 'backtest_results')
    json_candidates = [
        p for p in glob.glob(os.path.join(results_dir, 'backtest-result-*.json'))
        if not p.endswith('.meta.json')
    ]
    if json_candidates:
        json_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        latest = json_candidates[0]
        try:
            df = pd.read_json(latest)
            # If it's a dict-like dump, try to extract 'trades' key
            if isinstance(df, pd.DataFrame) and 'trades' in df.columns and len(df.columns) == 1:
                # df has a single column 'trades' with list-like content
                trades = pd.json_normalize(df['trades'].iloc[0])
                return trades
            if 'trades' in df:
                return pd.json_normalize(df['trades'])
        except Exception:
            pass

    # Fallback 2: .last_result.json
    last_path = os.path.join(results_dir, '.last_result.json')
    if os.path.exists(last_path):
        try:
            df = pd.read_json(last_path)
            if 'trades' in df:
                return pd.json_normalize(df['trades'])
            if isinstance(df, pd.DataFrame) and 'trades' in df.columns and len(df.columns) == 1:
                return pd.json_normalize(df['trades'].iloc[0])
        except Exception:
            pass

    # Fallback 3: latest backtest-result-*.zip, parse trades file within
    zip_candidates = sorted(
        glob.glob(os.path.join(results_dir, 'backtest-result-*.zip')),
        key=lambda p: os.path.getmtime(p), reverse=True
    )
    for zpath in zip_candidates:
        try:
            with zipfile.ZipFile(zpath, 'r') as zf:
                # Prefer trades CSVs
                entries = [zi for zi in zf.infolist() if not zi.is_dir()]
                # Heuristic: files containing 'trades' in name
                trade_entries = [e for e in entries if 'trade' in e.filename.lower()]
                if not trade_entries:
                    continue
                # Prefer CSV over JSON, then pick largest
                def key_fn(e):
                    is_csv = e.filename.lower().endswith('.csv')
                    is_json = e.filename.lower().endswith('.json')
                    return (0 if is_csv else (1 if is_json else 2), -e.file_size)
                trade_entries.sort(key=key_fn)
                chosen = trade_entries[0]
                with zf.open(chosen, 'r') as fh:
                    if chosen.filename.lower().endswith('.csv'):
                        return pd.read_csv(fh)
                    elif chosen.filename.lower().endswith('.json'):
                        # Could be dict with 'trades' key or list of trades
                        data = fh.read()
                        try:
                            df = pd.read_json(io.BytesIO(data))
                            if 'trades' in df:
                                return pd.json_normalize(df['trades'])
                            if isinstance(df, pd.DataFrame) and 'pair' in df.columns:
                                return df
                        except Exception:
                            pass
        except Exception:
            continue

    raise FileNotFoundError('No trades data found (CSV or JSON).')


def main():
    trades = load_trades_df()
    # Normalize dates
    for c in ['open_date', 'close_date']:
        if c in trades.columns:
            trades[c] = pd.to_datetime(trades[c], utc=True)

    # Determine pair from trades (fallback to BTC/USDT:USDT)
    pair = 'BTC/USDT:USDT'
    if 'pair' in trades.columns and not trades['pair'].empty:
        pair = str(trades['pair'].iloc[0])

    # Load OHLCV via Freqtrade utilities (futures 1m and 1h)
    df1m = load_ohlcv_via_freqtrade(pair=pair, timeframe='1m', candle_type='futures')
    df1h = load_ohlcv_via_freqtrade(pair=pair, timeframe='1h', candle_type='futures')

    if df1m.empty or df1h.empty:
        print("No OHLCV data found for", pair, "- please ensure data exists in user_data/data.")
        return

    df = compute_indicators(df1m, df1h)

    # Parameter references (matching strategy defaults/hyperopt best shown earlier)
    params = {
        'adx_period': 7,
        'adx_threshold': 25,
        'tema_period': 13,
        'ema_period': 200,
        'obv_ma_period': 30,
        'rsi_period': 10,
        'rsi_threshold': 50,
        'st_len': 13,
        'st_mult': 1.5,
        'atr_min_ratio': 0.0005,
        'max_ema_distance': 0.002,
    }

    # Build snapshots for each trade
    snapshots = []
    for _, t in trades.iterrows():
        o_ts = pd.to_datetime(t['open_date'], utc=True)
        c_ts = pd.to_datetime(t['close_date'], utc=True)
        o_row = snapshot_row(df, o_ts - pd.Timedelta(minutes=1))
        c_row = snapshot_row(df, c_ts)

        adx_col = f"adx_{params['adx_period']}"
        tema_col = f"tema_{params['tema_period']}"
        obv_ma_col = f"obv_ma_{params['obv_ma_period']}"
        rsi_col = f"rsi_{params['rsi_period']}"
        st_dir_col = f"supertrend_direction_{params['st_len']}_{params['st_mult']}"

        def ema_distance(row):
            ema = row['ema_200']
            if pd.isna(ema) or ema == 0:
                return np.nan
            return abs(row['close'] / ema - 1.0)

        entry = {
            'pair': t['pair'],
            'side': 'short' if t.get('is_short', False) or (t.get('direction') == 'short') else 'long',
            'open_date': o_ts,
            'close_date': c_ts,
            'profit_abs': t.get('profit_abs', np.nan),
            'profit_ratio': t.get('profit_ratio', np.nan),
            'exit_reason': t.get('exit_reason', ''),
            'adx': o_row.get(adx_col, np.nan),
            'tema_slope_up': (o_row.get(tema_col, np.nan) > df.loc[max(o_row.name-1,0), tema_col]) if tema_col in df.columns else np.nan,
            'tema_above_ema': (o_row.get(tema_col, np.nan) > o_row.get('ema_200', np.nan)),
            'macd_gt_signal': (o_row.get('macd', np.nan) > o_row.get('macdsignal', np.nan)),
            'macdhist': o_row.get('macdhist', np.nan),
            'rsi': o_row.get(rsi_col, np.nan),
            'st_dir': o_row.get(st_dir_col, np.nan),
            'obv_vs_ma': (o_row.get('obv', np.nan) - o_row.get(obv_ma_col, np.nan)),
            'atr_ratio': (o_row.get('atr', np.nan) / o_row.get('close', np.nan)),
            'ema_distance': ema_distance(o_row),
            'h1_trend_up': (o_row.get('close_1h', np.nan) > o_row.get('ema_200_1h', np.nan)) if 'close_1h' in o_row and 'ema_200_1h' in o_row else np.nan,
        }

        exit_snap = {
            'adx_e': c_row.get(adx_col, np.nan),
            'macdhist_e': c_row.get('macdhist', np.nan),
            'rsi_e': c_row.get(rsi_col, np.nan),
            'st_dir_e': c_row.get(st_dir_col, np.nan),
            'atr_ratio_e': (c_row.get('atr', np.nan) / c_row.get('close', np.nan)),
        }

        entry.update(exit_snap)
        snapshots.append(entry)

    snap = pd.DataFrame(snapshots)
    
    # === TRADE CLUSTERING BY PROFIT ===
    print("\n=== TRADE CLUSTERING BY PROFIT ===")
    
    # Define profit buckets
    profit_pct = snap['profit_ratio'] * 100
    
    big_winners = snap[profit_pct >= 0.4]  # >= 0.4%
    small_winners = snap[(profit_pct >= 0.2) & (profit_pct < 0.4)]  # 0.2-0.4%
    tiny_winners = snap[(profit_pct > 0) & (profit_pct < 0.2)]  # 0-0.2%
    tiny_losers = snap[(profit_pct >= -0.5) & (profit_pct <= 0)]  # 0 to -0.5%
    medium_losers = snap[(profit_pct >= -1.0) & (profit_pct < -0.5)]  # -0.5% to -1%
    big_losers = snap[profit_pct < -1.0]  # < -1%
    
    print(f"\nBIG WINNERS (≥0.4%): {len(big_winners)} trades, {big_winners['profit_abs'].sum():.2f} USDT total")
    print(f"SMALL WINNERS (0.2-0.4%): {len(small_winners)} trades, {small_winners['profit_abs'].sum():.2f} USDT total")
    print(f"TINY WINNERS (0-0.2%): {len(tiny_winners)} trades, {tiny_winners['profit_abs'].sum():.2f} USDT total")
    print(f"TINY LOSERS (0 to -0.5%): {len(tiny_losers)} trades, {tiny_losers['profit_abs'].sum():.2f} USDT total")
    print(f"MEDIUM LOSERS (-0.5% to -1%): {len(medium_losers)} trades, {medium_losers['profit_abs'].sum():.2f} USDT total")
    print(f"BIG LOSERS (<-1%): {len(big_losers)} trades, {big_losers['profit_abs'].sum():.2f} USDT total")
    
    # === Detailed cluster analysis ===
    print("\n=== CLUSTER PATTERN ANALYSIS ===")
    
    for cluster_name, cluster_df in [
        ("BIG WINNERS (≥0.4%)", big_winners),
        ("SMALL WINNERS (0.2-0.4%)", small_winners),
        ("TINY WINNERS (0-0.2%)", tiny_winners),
        ("TINY LOSERS (0 to -0.5%)", tiny_losers),
        ("MEDIUM LOSERS (-0.5% to -1%)", medium_losers),
        ("BIG LOSERS (<-1%)", big_losers),
    ]:
        if len(cluster_df) == 0:
            continue
            
        print(f"\n{cluster_name}: {len(cluster_df)} trades")
        print(f"  Avg ADX: {cluster_df['adx'].mean():.1f} (min: {cluster_df['adx'].min():.1f}, max: {cluster_df['adx'].max():.1f})")
        print(f"  Avg RSI: {cluster_df['rsi'].mean():.1f} (min: {cluster_df['rsi'].min():.1f}, max: {cluster_df['rsi'].max():.1f})")
        print(f"  Avg MACD hist: {cluster_df['macdhist'].mean():.2f}")
        print(f"  Avg ATR/Close: {cluster_df['atr_ratio'].mean():.5f}")
        print(f"  Avg EMA dist: {cluster_df['ema_distance'].mean():.5f}")
        dur_mins = (cluster_df['close_date'] - cluster_df['open_date']).dt.total_seconds() / 60
        print(f"  Avg duration: {dur_mins.mean():.0f} minutes")
        
        # Exit breakdown
        exits = cluster_df['exit_reason'].value_counts()
        print(f"  Exit reasons: {dict(exits)}")
        
        # Side breakdown
        sides = cluster_df['side'].value_counts()
        print(f"  Sides: {dict(sides)}")

    # Sort to get worst/best
    worst = snap.sort_values('profit_ratio').head(20)
    best = snap.sort_values('profit_ratio', ascending=False).head(20)

    def fmt_row(r):
        return {
            'open': r['open_date'],
            'close': r['close_date'],
            'side': r['side'],
            'profit%': round(float(r['profit_ratio'])*100, 3) if pd.notna(r['profit_ratio']) else np.nan,
            'exit': r['exit_reason'],
            'ADX': round(r['adx'], 2) if pd.notna(r['adx']) else np.nan,
            'RSI': round(r['rsi'], 1) if pd.notna(r['rsi']) else np.nan,
            'MACDh': round(r['macdhist'], 5) if pd.notna(r['macdhist']) else np.nan,
            'OBV-OBVma': round(r['obv_vs_ma'], 0) if pd.notna(r['obv_vs_ma']) else np.nan,
            'ATR/Close': round(r['atr_ratio'], 5) if pd.notna(r['atr_ratio']) else np.nan,
            '|close-EMA200|/EMA200': round(r['ema_distance'], 5) if pd.notna(r['ema_distance']) else np.nan,
            'H1 up?': bool(r['h1_trend_up']) if pd.notna(r['h1_trend_up']) else None,
            'ST dir': int(r['st_dir']) if pd.notna(r['st_dir']) else None,
        }

    print("\n=== 20 WORST TRADES (diagnostics) ===")
    for _, r in worst.iterrows():
        print(fmt_row(r))

    print("\n=== 20 BEST TRADES (diagnostics) ===")
    for _, r in best.iterrows():
        print(fmt_row(r))

    # Aggregate heuristics: losers with near-threshold values
    losers = snap[snap['profit_ratio'] < 0]
    winners = snap[snap['profit_ratio'] > 0]

    def share(cond: pd.Series) -> float:
        if len(cond) == 0:
            return np.nan
        return round(100 * cond.mean(), 1)

    agg = {
        'losers_low_adx_%': share(losers['adx'] < (params['adx_threshold'] + 3)),
        'losers_low_atr_%': share(losers['atr_ratio'] < (params['atr_min_ratio'] * 1.2)),
        'losers_far_ema_%': share(losers['ema_distance'] > (params['max_ema_distance'] * 0.9)),
        'losers_macd_neg_%': share(losers['macdhist'] <= 0),
        'losers_obv_below_ma_%': share(losers['obv_vs_ma'] <= 0),
        'losers_h1_against_%': share(losers['h1_trend_up'] == False),
        'winners_strong_adx_%': share(winners['adx'] >= (params['adx_threshold'] + 5)),
        'winners_high_atr_%': share(winners['atr_ratio'] >= (params['atr_min_ratio'] * 1.5)),
        'winners_close_to_ema_%': share(winners['ema_distance'] <= (params['max_ema_distance'] * 0.7)),
        'winners_macd_pos_%': share(winners['macdhist'] > 0),
        'winners_obv_above_ma_%': share(winners['obv_vs_ma'] > 0),
        'winners_h1_with_%': share(winners['h1_trend_up'] == True),
    }
    print("\n=== Aggregate heuristics ===")
    for k, v in agg.items():
        print(f"{k}: {v}%")


if __name__ == '__main__':
    # Simple watchdog to avoid hangs
    import threading
    import time
    TIMEOUT_SECONDS = int(os.environ.get('QTS_ANALYZER_TIMEOUT', '240'))
    aborted = {'flag': False}

    def _abort():
        aborted['flag'] = True
        try:
            print('\nAnalyzer timeout exceeded. Exiting...')
        finally:
            os._exit(3)

    timer = threading.Timer(TIMEOUT_SECONDS, _abort)
    timer.daemon = True
    timer.start()
    try:
        main()
    finally:
        timer.cancel()



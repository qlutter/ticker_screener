from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class ScreenResult:
    ticker: str
    name: str
    sector: str
    price: float
    itp: float
    fv: float
    ap: float
    scenario_pt: float
    buy_max: float
    mos_itp: float
    signal_score: float
    ta_score: float
    implied_growth: float
    mes: float
    zone: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_tickers(ticker_file: str | Path, sort_mode: str = "keep") -> list[str]:
    path = Path(ticker_file)
    if not path.exists():
        raise FileNotFoundError(f"ticker 파일이 없습니다: {path}")

    tickers: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        ticker = line.upper()
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)

    if sort_mode == "asc":
        tickers.sort()
    elif sort_mode == "desc":
        tickers.sort(reverse=True)
    elif sort_mode != "keep":
        raise ValueError(f"지원하지 않는 sort_mode: {sort_mode}")

    return tickers


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def _safe_geom_mean(values: list[float], floor: float = 1e-6) -> float:
    vals = [max(float(v), floor) for v in values if v is not None and np.isfinite(v)]
    if not vals:
        return floor
    return float(np.exp(np.mean(np.log(vals))))


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.bfill().fillna(50.0)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean().bfill()


def compute_vwap_proxy(df: pd.DataFrame) -> float:
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    volume = df["Volume"].fillna(0.0)
    denom = float(volume.sum())
    if denom <= 0:
        return float(df["Close"].iloc[-1])
    return float((typical * volume).sum() / denom)


def compute_volume_profile_anchor(df: pd.DataFrame, bins: int = 24) -> float:
    closes = df["Close"].dropna()
    volumes = df["Volume"].reindex(closes.index).fillna(0.0)
    if len(closes) < 10:
        return float(df["Close"].iloc[-1])

    price_min = float(closes.min())
    price_max = float(closes.max())
    if price_max <= price_min:
        return float(closes.iloc[-1])

    hist, edges = np.histogram(
        closes.values,
        bins=bins,
        range=(price_min, price_max),
        weights=volumes.values,
    )
    idx = int(np.argmax(hist))
    return float((edges[idx] + edges[idx + 1]) / 2.0)


def compute_support_anchor(df: pd.DataFrame) -> float:
    close = df["Close"]
    ma20 = close.rolling(20, min_periods=1).mean().iloc[-1]
    ma50 = close.rolling(50, min_periods=1).mean().iloc[-1]
    ma100 = close.rolling(100, min_periods=1).mean().iloc[-1]
    return float(np.median([ma20, ma50, ma100]))


def compute_ap(df: pd.DataFrame) -> float:
    return float(np.mean([compute_vwap_proxy(df), compute_volume_profile_anchor(df), compute_support_anchor(df)]))


def compute_fv(info: dict[str, Any], price: float) -> tuple[float, float]:
    trailing_pe = _safe_float(info.get("trailingPE"), 0.0)
    forward_pe = _safe_float(info.get("forwardPE"), 0.0)
    price_to_book = _safe_float(info.get("priceToBook"), 0.0)
    roe = _safe_float(info.get("returnOnEquity"), 0.0)
    profit_margin = _safe_float(info.get("profitMargins"), 0.0)
    revenue_growth = _safe_float(info.get("revenueGrowth"), 0.0)
    earnings_growth = _safe_float(info.get("earningsGrowth"), 0.0)

    growth_candidates = [revenue_growth, earnings_growth, profit_margin * 0.5, roe * 0.25]
    clean_growth = [g for g in growth_candidates if np.isfinite(g)]
    implied_growth = float(np.nanmean(clean_growth)) if clean_growth else 0.0
    implied_growth = _clip(implied_growth, -0.20, 0.60)

    if trailing_pe > 0:
        rim = price * (1.0 + roe * 0.60)
    else:
        rim = price * (1.0 + max(roe, 0.0) * 0.35)

    if forward_pe > 0:
        econ_profit = price * (1.0 + max(0.0, (25.0 - forward_pe) / 100.0) + max(roe, 0.0) * 0.20)
    elif trailing_pe > 0:
        econ_profit = price * (1.0 + max(0.0, (28.0 - trailing_pe) / 120.0))
    else:
        econ_profit = price

    if price_to_book > 0:
        reverse_dcf = price * (1.0 + implied_growth * 1.8 - max(0.0, price_to_book - 6.0) * 0.03)
    else:
        reverse_dcf = price * (1.0 + implied_growth * 1.2)

    fv = _safe_geom_mean([rim, econ_profit, reverse_dcf], floor=max(price * 0.1, 1e-6))
    return float(max(fv, price * 0.35)), float(implied_growth)


def compute_mes(info: dict[str, Any], df: pd.DataFrame, implied_growth: float) -> float:
    trailing_pe = _safe_float(info.get("trailingPE"), 0.0)
    forward_pe = _safe_float(info.get("forwardPE"), 0.0)
    beta = _safe_float(info.get("beta"), 1.0)
    close = df["Close"]
    ma20 = close.rolling(20, min_periods=1).mean().iloc[-1]
    ma50 = close.rolling(50, min_periods=1).mean().iloc[-1]
    momentum = (ma20 / ma50 - 1.0) if ma50 > 0 else 0.0

    valuation_room = 0.0
    if forward_pe > 0:
        valuation_room = (30.0 - forward_pe) / 30.0
    elif trailing_pe > 0:
        valuation_room = (35.0 - trailing_pe) / 35.0

    raw = (
        0.45 * _clip(implied_growth / 0.30, -1.0, 1.0)
        + 0.35 * _clip(valuation_room, -1.0, 1.0)
        + 0.20 * _clip(momentum / 0.15, -1.0, 1.0)
        - 0.10 * max(0.0, beta - 1.8)
    )
    return _clip(0.5 + raw * 0.25, 0.0, 1.0)


def compute_scenario_pt(price: float, fv: float, ap: float, mes: float, catalyst_premium: float) -> float:
    bear = 0.55 * fv + 0.45 * ap
    base = 0.70 * fv + 0.30 * ap
    bull = max(base, fv * (1.10 + 0.35 * mes + catalyst_premium))
    weights = np.array([0.20, 0.55, 0.25], dtype=float)
    scenario_pt = float(np.dot(np.array([bear, base, bull], dtype=float), weights))
    return max(scenario_pt, price * 0.50)


def compute_ta_score(df: pd.DataFrame) -> float:
    close = df["Close"]
    latest_close = float(close.iloc[-1])
    ma20 = float(close.rolling(20, min_periods=1).mean().iloc[-1])
    ma50 = float(close.rolling(50, min_periods=1).mean().iloc[-1])
    ma200 = float(close.rolling(200, min_periods=1).mean().iloc[-1])
    rsi = float(compute_rsi(close).iloc[-1])
    atr = float(compute_atr(df).iloc[-1])
    atr_ratio = atr / latest_close if latest_close > 0 else 0.0

    trend_score = 0.0
    trend_score += 15.0 if latest_close > ma20 else 0.0
    trend_score += 20.0 if latest_close > ma50 else 0.0
    trend_score += 20.0 if latest_close > ma200 else 0.0
    trend_score += 10.0 if ma20 > ma50 else 0.0
    trend_score += 10.0 if ma50 > ma200 else 0.0

    if 45 <= rsi <= 65:
        rsi_score = 20.0
    elif 35 <= rsi < 45 or 65 < rsi <= 75:
        rsi_score = 12.0
    elif 25 <= rsi < 35 or 75 < rsi <= 82:
        rsi_score = 6.0
    else:
        rsi_score = 0.0

    vol_score = 5.0 if atr_ratio <= 0.035 else 0.0
    return _clip(trend_score + rsi_score + vol_score, 0.0, 100.0)


def determine_zone(price: float, buy_max: float, ap: float, ta_score: float) -> str:
    if price <= buy_max * 0.92 and ta_score >= 55:
        return "STRONG_BUY"
    if price <= buy_max and ta_score >= 45:
        return "BUY"
    if price <= ap * 1.05:
        return "WATCH"
    return "HOLD"


def compute_signal_score(price: float, itp: float, buy_max: float, ta_score: float, mes: float) -> tuple[float, float]:
    mos_itp = ((itp / price) - 1.0) * 100.0 if price > 0 else 0.0
    value_component = _clip((mos_itp + 25.0) / 50.0, 0.0, 1.0) * 45.0
    if buy_max > 0 and price <= buy_max:
        buy_component = 20.0
    elif buy_max > 0:
        buy_component = max(0.0, 20.0 - ((price / buy_max) - 1.0) * 100.0)
    else:
        buy_component = 0.0
    ta_component = _clip(ta_score / 100.0, 0.0, 1.0) * 25.0
    mes_component = _clip(mes, 0.0, 1.0) * 10.0
    score = value_component + buy_component + ta_component + mes_component
    return _clip(score, 0.0, 100.0), mos_itp


def fetch_history_and_info(ticker: str, period: str = "1y") -> tuple[pd.DataFrame, dict[str, Any]]:
    tk = yf.Ticker(ticker)
    hist = tk.history(period=period, auto_adjust=False)
    if hist is None or hist.empty:
        raise ValueError("시세 데이터를 가져오지 못했습니다")

    hist = hist.copy()
    hist.columns = [str(c) for c in hist.columns]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in hist.columns:
            raise ValueError(f"필수 컬럼 누락: {col}")

    hist = hist.dropna(subset=["Close"])
    if len(hist) < 60:
        raise ValueError("시세 데이터가 부족합니다")

    try:
        info = tk.fast_info or {}
    except Exception:
        info = {}
    if not info:
        try:
            info = tk.info or {}
        except Exception:
            info = {}
    return hist, info


def build_note(price: float, itp: float, buy_max: float, ta_score: float, zone: str) -> str:
    if zone == "STRONG_BUY":
        return f"현재가가 보수적 매수상한(${buy_max:.2f}) 아래에 있고 TA 점수({ta_score:.1f})도 양호합니다."
    if zone == "BUY":
        return f"현재가가 매수상한(${buy_max:.2f}) 근처/이하에 있어 분할 진입 검토 구간입니다."
    if price < itp:
        return "가치상 할인 상태지만 기술적 타이밍 확인이 더 필요합니다."
    return "업사이드보다 추격 리스크가 커 보여 관찰 우선이 적절합니다."


def analyze_ticker(ticker: str, settings: dict[str, Any], logger: logging.Logger) -> ScreenResult:
    sector_name = str(settings.get("sector_name", "custom"))
    catalyst_premium = _safe_float(settings.get("catalyst_premium"), 0.04)

    hist, info = fetch_history_and_info(ticker)
    price = float(hist["Close"].iloc[-1])
    name = str(info.get("shortName") or info.get("longName") or info.get("displayName") or ticker)

    fv, implied_growth = compute_fv(info, price)
    ap = compute_ap(hist)
    mes = compute_mes(info, hist, implied_growth)
    scenario_pt = compute_scenario_pt(price, fv, ap, mes, catalyst_premium)
    itp = _safe_geom_mean([fv, ap, scenario_pt], floor=max(price * 0.1, 1e-6))

    model_spread = np.std([fv, ap, scenario_pt]) / max(np.mean([fv, ap, scenario_pt]), 1e-6)
    safety_margin = 0.12 + min(model_spread, 0.20)
    buy_max = itp * (1.0 - safety_margin)

    ta_score = compute_ta_score(hist)
    signal_score, mos_itp = compute_signal_score(price, itp, buy_max, ta_score, mes)
    zone = determine_zone(price, buy_max, ap, ta_score)
    note = build_note(price, itp, buy_max, ta_score, zone)

    return ScreenResult(
        ticker=ticker,
        name=name,
        sector=sector_name,
        price=float(price),
        itp=float(itp),
        fv=float(fv),
        ap=float(ap),
        scenario_pt=float(scenario_pt),
        buy_max=float(buy_max),
        mos_itp=float(mos_itp),
        signal_score=float(signal_score),
        ta_score=float(ta_score),
        implied_growth=float(implied_growth),
        mes=float(mes),
        zone=zone,
        note=note,
    )


def run_screen(tickers: list[str], settings: dict[str, Any], logger: logging.Logger) -> list[ScreenResult]:
    results: list[ScreenResult] = []
    total = len(tickers)
    for idx, ticker in enumerate(tickers, start=1):
        try:
            row = analyze_ticker(ticker=ticker, settings=settings, logger=logger)
            results.append(row)
            logger.info(
                "[%d/%d] %s 완료 | P=%.2f ITP=%.2f MOS=%+.1f%% Sig=%.1f %s",
                idx,
                total,
                ticker,
                row.price,
                row.itp,
                row.mos_itp,
                row.signal_score,
                row.zone,
            )
        except Exception as exc:
            logger.warning("[%d/%d] %s 실패: %s", idx, total, ticker, exc)

    results.sort(key=lambda r: (r.signal_score, r.mos_itp, r.ta_score), reverse=True)
    return results

"""
BOT DE ALERTAS DE TRADING - EMA Crossover + RSI
Para XAUUSD (oro) y EURUSD
Envía alertas a Telegram, NO ejecuta órdenes automáticamente.

REQUISITOS:
pip install yfinance pandas requests --break-system-packages

CONFIGURACIÓN DE NOTIFICACIONES (ntfy.sh - gratis, sin registro):
1. Descarga la app "ntfy" (disponible en App Store / Play Store)
2. Abre la app, toca "+" para suscribirte a un "topic" (canal)
3. Ponle un nombre ÚNICO y secreto, ej: "sair-trading-alerts-9284"
4. Pega ese mismo nombre en NTFY_TOPIC abajo
5. Listo, las alertas llegan como notificación push a tu celular

CÓMO CORRERLO 24/7 GRATIS:
- Sube este archivo a Railway.app o Render.com (plan free)
- O en tu PC con: nohup python3 trading_alert_bot.py &
"""

import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime

# ============ CONFIGURACIÓN ============
NTFY_TOPIC = "sair-trading-alerts-9284"

SYMBOLS = {
    "XAUUSD": "XAU=X",   # Oro spot (proxy de XAUUSD)
    "EURUSD": "EURUSD=X"
}

EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

CHECK_INTERVAL_SECONDS = 900  # cada 15 minutos
INTERVAL = "15m"   # temporalidad de las velas
LOOKBACK = "5d"    # historial a descargar

# ============ FUNCIONES ============

def send_telegram(message):
    """Envía la alerta como notificación push vía ntfy.sh (nombre mantenido por compatibilidad)."""
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "Alerta de Trading Bot"},
            timeout=10
        )
    except Exception as e:
        print(f"Error enviando notificación: {e}")


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def get_data(ticker, retries=3):
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period=LOOKBACK, interval=INTERVAL, progress=False, auto_adjust=True)
            if df is not None and not df.empty:
                break
        except Exception:
            df = None
        time.sleep(5)
    else:
        return None
    if df is None or df.empty:
        return None
    # yfinance a veces devuelve columnas multi-nivel; las aplanamos
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df["EMA_fast"] = df["Close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["EMA_slow"] = df["Close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["RSI"] = calculate_rsi(df["Close"], RSI_PERIOD)
    return df


def check_signal(df, name):
    if df is None or len(df) < EMA_SLOW + 2:
        return None

    prev = df.iloc[-2]
    last = df.iloc[-1]

    prev_fast = float(prev["EMA_fast"])
    prev_slow = float(prev["EMA_slow"])
    last_fast = float(last["EMA_fast"])
    last_slow = float(last["EMA_slow"])

    cross_up = prev_fast <= prev_slow and last_fast > last_slow
    cross_down = prev_fast >= prev_slow and last_fast < last_slow

    rsi = float(last["RSI"])
    price = float(last["Close"])

    if cross_up:
        nota = " (RSI sobrevendido, señal más fuerte)" if rsi < RSI_OVERSOLD else ""
        return f"🟢 {name}: EMA{EMA_FAST} cruzó ARRIBA de EMA{EMA_SLOW}. Precio: {price:.4f} | RSI: {rsi:.1f}{nota}\nPosible señal de COMPRA."

    if cross_down:
        nota = " (RSI sobrecomprado, señal más fuerte)" if rsi > RSI_OVERBOUGHT else ""
        return f"🔴 {name}: EMA{EMA_FAST} cruzó ABAJO de EMA{EMA_SLOW}. Precio: {price:.4f} | RSI: {rsi:.1f}{nota}\nPosible señal de VENTA."

    return None


def run_once():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Revisando mercados...")
    for name, ticker in SYMBOLS.items():
        try:
            df = get_data(ticker)
            signal = check_signal(df, name)
            if signal:
                print(signal)
                send_telegram(signal)
            else:
                print(f"{name}: sin señal nueva.")
        except Exception as e:
            print(f"Error con {name}: {e}")


def main():
    send_telegram("🤖 Bot de alertas iniciado. Monitoreando XAUUSD y EURUSD cada 15 min.")
    while True:
        run_once()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

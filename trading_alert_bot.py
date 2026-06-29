"""
BOT DE ALERTAS DE TRADING - EMA Crossover + RSI
Para XAUUSD (oro) y EURUSD
Envía alertas a Telegram, NO ejecuta órdenes automáticamente.

REQUISITOS:
pip install yfinance pandas requests --break-system-packages

CONFIGURACIÓN CORREO (Gmail):
1. Ve a https://myaccount.google.com/apppasswords (necesitas verificación en 2 pasos activada)
2. Crea una contraseña de aplicación, te da un código de 16 letras
3. Pega tu correo en EMAIL_FROM y el código (sin espacios) en EMAIL_APP_PASSWORD
4. Pega el correo donde quieres recibir alertas en EMAIL_TO (puede ser el mismo)

CÓMO CORRERLO 24/7 GRATIS:
- Sube este archivo a Railway.app o Render.com (plan free)
- O en tu PC con: nohup python3 trading_alert_bot.py &
"""

import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
import time
from datetime import datetime

# ============ CONFIGURACIÓN ============
EMAIL_FROM = "saircure@gmail.com"
EMAIL_APP_PASSWORD = "soeqmdsupbsrsvpv"
EMAIL_TO = "saircure@gmail.com"

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
    """Envía la alerta por correo (se mantiene el nombre para no romper el resto del código)."""
    if "PEGA_TU" in EMAIL_APP_PASSWORD:
        print("[AVISO] No configuraste la contraseña de aplicación de Gmail. Mensaje no enviado:")
        print(message)
        return
    try:
        msg = MIMEText(message)
        msg["Subject"] = "🔔 Alerta de Trading Bot"
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Error enviando correo: {e}")


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

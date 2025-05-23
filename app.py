
from flask import Flask, render_template
import requests
import pandas as pd
import ta
import numpy as np
from datetime import datetime, timedelta
import threading
import time
from config import CONFIG

app = Flask(__name__)
app.secret_key = CONFIG['FLASK_SECRET_KEY']

signals = []

def fetch_15m_data(symbol):
    """جلب بيانات 15 دقيقة من Bybit"""
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=15"
        response = requests.get(url)
        data = response.json()
        df = pd.DataFrame(data['result']['list'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching 15m data: {str(e)}")
        return None

def analyze_short_term(df, symbol):
    """تحليل الإطار الزمني القصير"""
    try:
        # تحويل الأعمدة الرقمية
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # حساب المؤشرات السريعة
        df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
        df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
        df['rsi_14'] = ta.momentum.rsi(df['close'], window=14)
        df['macd'] = ta.trend.macd(df['close'])
        
        # تحديد نقاط الدخول
        last_row = df.iloc[-1]
        entry_signal = None
        
        # شروط الشراء السريع
        if (last_row['ema_9'] > last_row['ema_21'] and 
            last_row['rsi_14'] < 65 and 
            last_row['macd'] > 0):
            
            entry_time = datetime.utcnow() + timedelta(minutes=1)  # وقت الدخول المقترح
            entry_signal = {
                'symbol': symbol,
                'signal': 'BUY',
                'entry_price': last_row['close'],
                'target': round(last_row['close'] * 1.005, 4),  # +0.5%
                'stop_loss': round(last_row['close'] * 0.995, 4),  # -0.5%
                'entry_time': entry_time.strftime("%H:%M UTC"),
                'expiry_time': (entry_time + timedelta(minutes=30)).strftime("%H:%M UTC"),
                'timeframe': '15m',
                'confidence': np.random.randint(70, 90)  # قيمة عشوائية للتمثيل
            }
        
        return entry_signal
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return None

def scan_opportunities():
    global signals
    while True:
        try:
            # جلب قائمة جميع الأزواج
            tickers = requests.get(CONFIG['TICKERS_URL']).json()['result']['list']
            top_pairs = [ticker['symbol'] for ticker in tickers if float(ticker['volume24h']) > 1000000][:10]
            
            current_signals = []
            for pair in top_pairs:
                df = fetch_15m_data(pair)
                if df is not None:
                    signal = analyze_short_term(df, pair)
                    if signal:
                        current_signals.append(signal)
            
            signals = sorted(current_signals, key=lambda x: x['confidence'], reverse=True)
            
        except Exception as e:
            print(f"Scan error: {str(e)}")
        
        time.sleep(CONFIG['SCAN_INTERVAL'])

@app.route('/')
def short_term_signals():
    return render_template('short_term.html', signals=signals)

if __name__ == '__main__':
    threading.Thread(target=scan_opportunities, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

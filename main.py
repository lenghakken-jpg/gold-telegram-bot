import os
import sys
import time
import requests
import feedparser
import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

# ------------------ TELEGRAM CONFIG & CHAT IDs ------------------
TELEGRAM_TOKEN = "8463972884:AAHPQYAuVgQMOxl740L9MbUPSE7KHk4wPa4"

SIGNAL_CHAT_ID = "-1004453506421"  # Group ទី ១: សម្រាប់ SMC Signal (1:3 RRR)
NEWS_CHAT_ID   = "-1004336663386"  # Group ទី ២: សម្រាប់ News Alerts ស្វ័យប្រវត្តិ

GOLD_TICKER = 'GC=F'        # XAU/USD (Gold Futures)
TIMEFRAME = '15m'           # Entry Timeframe
HTF = '1h'                  # Higher Timeframe Trend

last_signal = None
sent_news_ids = set()

# ------------------ TELEGRAM FUNCTIONS ------------------

def send_signal_telegram(message):
    """ផ្ញើសារ Signal ទិញ/លក់ ចូល Group ទី ១"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": SIGNAL_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        print("✅ ផ្ញើសារ Signal ចូល Telegram បានជោគជ័យ!")
    except Exception as e:
        print(f"❌ មានបញ្ហាក្នុងការផ្ញើសារ Signal: {e}")

def send_news_telegram(title, link, published, source_name="Yahoo Finance"):
    """ផ្ញើសារព័ត៌មានមាស ចូល Group ទី ២"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    msg = (
        f"📰 <b>បច្ចុប្បន្នភាពព័ត៌មានទីផ្សារមាស</b> [{source_name}]\n\n"
        f"📌 <b>{title}</b>\n\n"
        f"🕒 <i>កាលបរិច្ឆេទ: {published}</i>\n"
        f"🔗 <a href='{link}'>ចុចទីនេះដើម្បីអានព័ត៌មានលម្អិត</a>"
    )
    
    payload = {
        "chat_id": NEWS_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ ផ្ញើសារព័ត៌មានចូល Group ទី ២ រួចរាល់: {title[:30]}...")
        else:
            print(f"❌ ការផ្ញើសារព័ត៌មានបរាជ័យ: {res.text}")
    except Exception as e:
        print(f"❌ មានបញ្ហាក្នុងការផ្ញើសារព័ត៌មាន: {e}")

# ------------------ NEWS SCRAPER MODULE ------------------

def fetch_and_send_gold_news():
    """Scrape ព័ត៌មានមាសស្វ័យប្រវត្តិ និងផ្ញើចូល Group ទី ២"""
    global sent_news_ids
    
    news_feeds = [
        ("ព័ត៌មានមាស Google", "https://news.google.com/rss/search?q=gold+price+XAUUSD&hl=en-US&gl=US&ceid=US:en"),
        ("ព័ត៌មានអត្រាការប្រាក់ Fed", "https://news.google.com/rss/search?q=gold+market+fed+interest+rates&hl=en-US&gl=US&ceid=US:en")
    ]
    
    for source_name, feed_url in news_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                news_id = entry.get('id', entry.get('link'))
                
                if news_id not in sent_news_ids:
                    title = entry.get('title', 'គ្មានចំណងជើង')
                    link = entry.get('link', '#')
                    published = entry.get('published', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    send_news_telegram(title, link, published, source_name)
                    sent_news_ids.add(news_id)
                    time.sleep(2)
        except Exception as e:
            print(f"⚠️ បញ្ហាក្នុងការទាញយក RSS feed ({source_name}): {e}")

# ------------------ DATA & TECHNICAL ANALYSIS ------------------

def get_gold_data(interval, period='5d'):
    try:
        df = yf.download(tickers=GOLD_TICKER, period=period, interval=interval, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df.rename(columns={
            'Datetime': 'timestamp', 'Date': 'timestamp',
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        }, inplace=True)
        return df
    except Exception as e:
        print(f"⚠️ បញ្ហាក្នុងការទាញយកទិន្នន័យ: {e}")
        return None

def analyze_smc_risk_profiles():
    global last_signal
    start_time = time.time()

    df = get_gold_data(interval=TIMEFRAME, period='5d')
    df_htf = get_gold_data(interval=HTF, period='10d')

    if df is None or df_htf is None:
        print("⚠️ មិនអាចទាញយកទិន្នន័យពី Yahoo Finance បានទេ។ កំពុងរំលងវគ្គនេះ...")
        return

    if len(df) < 50 or len(df_htf) < 5:
        print("⚠️ ប្រវែងទិន្នន័យខ្លីពេក។ កំពុងរំលងវគ្គនេះ...")
        return

    # Calculate Technical Indicators
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)

    latest = df.iloc[-2]
    close_price = latest['close']
    atr_val = latest['ATR']

    if pd.isna(atr_val) or pd.isna(close_price):
        return

    # 1. Psychological Level Filter
    psych_level = round(close_price / 10) * 10
    near_psych = abs(close_price - psych_level) <= (atr_val * 0.4)

    # 2. Key Levels
    lookback = df.iloc[-50:-2]
    swing_high = lookback['high'].max()
    swing_low = lookback['low'].min()

    # 3. Order Block Detection
    bullish_ob, bearish_ob = False, False
    for i in range(-6, -2):
        if df.iloc[i+1]['close'] > df.iloc[i+1]['open'] + (df.iloc[i+1]['ATR'] * 1.1):
            if df.iloc[i]['close'] < df.iloc[i]['open']:
                if df.iloc[i]['low'] <= close_price <= df.iloc[i]['high'] * 1.002:
                    bullish_ob = True

        if df.iloc[i+1]['close'] < df.iloc[i+1]['open'] - (df.iloc[i+1]['ATR'] * 1.1):
            if df.iloc[i]['close'] > df.iloc[i]['open']:
                if df.iloc[i]['low'] * 0.998 <= close_price <= df.iloc[i]['high']:
                    bearish_ob = True

    # 4. Quasimodo Pattern Detection
    qml_buy, qml_sell = False, False
    p_highs = df['high'].iloc[-20:-2].values
    p_lows = df['low'].iloc[-20:-2].values

    if len(p_highs) >= 15:
        left_shoulder_h = p_highs[-15]
        head_h = max(p_highs[-12:-5])
        if head_h > left_shoulder_h and abs(close_price - left_shoulder_h) <= (atr_val * 0.5):
            qml_sell = True

        left_shoulder_l = p_lows[-15]
        head_l = min(p_lows[-12:-5])
        if head_l < left_shoulder_l and abs(close_price - left_shoulder_l) <= (atr_val * 0.5):
            qml_buy = True

    # 5. HTF Trend (1H)
    htf_ema_series = ta.ema(df_htf['close'], length=200)
    if htf_ema_series is None or htf_ema_series.empty or pd.isna(htf_ema_series.iloc[-1]):
        htf_trend_up = True
    else:
        htf_trend_up = df_htf.iloc[-1]['close'] > htf_ema_series.iloc[-1]

    # 6. Confluence Evaluation
    confluences = []
    buy_score, sell_score = 0, 0

    if htf_trend_up:
        buy_score += 25
        confluences.append("ទំនោរទីផ្សារឡើងលើទំហំធំ (1H Bullish HTF)")
    else:
        sell_score += 25
        confluences.append("ទំនោរទីផ្សារចុះក្រោមទំហំធំ (1H Bearish HTF)")

    if bullish_ob:
        buy_score += 25
        confluences.append("តំបន់ទិញ Order Block (Bullish OB)")
    if bearish_ob:
        sell_score += 25
        confluences.append("តំបន់លក់ Order Block (Bearish OB)")

    if qml_buy:
        buy_score += 25
        confluences.append("ទម្រង់តម្លៃឡើង Quasimodo Pattern")
    if qml_sell:
        sell_score += 25
        confluences.append("ទម្រង់តម្លៃចុះ Quasimodo Pattern")

    if near_psych:
        buy_score += 15
        sell_score += 15
        confluences.append(f"កម្រិតតម្លៃចិត្តសាស្ត្រ (${psych_level})")

    # Risk Management (RRR 1:3)
    sl_distance = round(atr_val * 1.2, 2)
    tp_distance = round(sl_distance * 3, 2)
    execution_time = round(time.time() - start_time, 2)

    print(f"[{latest['timestamp']}] XAU/USD: ${close_price:.2f} | ពិនិត្យទិញ: {buy_score}% | ពិនិត្យលក់: {sell_score}%")

    # ------------------ BUY SIGNAL ------------------
    if buy_score >= 65 and last_signal != f"BUY_{latest['timestamp']}":
        profile_type = "ហានិភ័យទាប / ផលចំណេញខ្ពស់" if buy_score >= 75 else "ហានិភ័យខ្ពស់ / ផលចំណេញខ្ពស់"
        tp_price = round(close_price + tp_distance, 2)
        sl_price = round(close_price - sl_distance, 2)

        msg = (
            f"🔥 <b>សញ្ញា ទិញ (BUY) XAU/USD ({profile_type})</b> 🔥\n\n"
            f"🎯 <b>កម្រិតជោគជ័យប៉ាន់ស្មាន:</b> {buy_score}%\n"
            f"⚖️ <b>ផលធៀបហានិភ័យ/ផលចំណេញ (RRR):</b> 1:3\n"
            f"⏱ <b>រយៈពេលវិភាគ:</b> {execution_time}s\n\n"
            f"💰 <b>តម្លៃចូល (Entry Price):</b> ${close_price:.2f}\n"
            f"🎯 <b>គោលដៅប្រាក់ចំណេញ (Take Profit):</b> ${tp_price:.2f} (+${tp_distance})\n"
            f"🛑 <b>ចំណុចកាត់ខាត (Stop Loss):</b> ${sl_price:.2f} (-${sl_distance})\n\n"
            f"🧠 <b>មូលហេតុ និងសញ្ញាបញ្ជាក់:</b>\n" + "\n".join([f"• {c}" for c in confluences]) + "\n\n"
            f"🛡 <b>តំបន់ទ្រទ្រង់សំខាន់ (Key Support):</b> ${swing_low:.2f}\n"
            f"⚠️ <i>ចំណាំ៖ ការជួញដូរមានហានិភ័យ សូមគ្រប់គ្រងដើមទុនឱ្យបានម៉ត់ចត់។</i>"
        )
        send_signal_telegram(msg)
        last_signal = f"BUY_{latest['timestamp']}"

    # ------------------ SELL SIGNAL ------------------
    elif sell_score >= 65 and last_signal != f"SELL_{latest['timestamp']}":
        profile_type = "ហានិភ័យទាប / ផលចំណេញខ្ពស់" if sell_score >= 75 else "ហានិភ័យខ្ពស់ / ផលចំណេញខ្ពស់"
        tp_price = round(close_price - tp_distance, 2)
        sl_price = round(close_price + sl_distance, 2)

        msg = (
            f"🔥 <b>សញ្ញា លក់ (SELL) XAU/USD ({profile_type})</b> 🔥\n\n"
            f"🎯 <b>កម្រិតជោគជ័យប៉ាន់ស្មាន:</b> {sell_score}%\n"
            f"⚖️ <b>ផលធៀបហានិភ័យ/ផលចំណេញ (RRR):</b> 1:3\n"
            f"⏱ <b>រយៈពេលវិភាគ:</b> {execution_time}s\n\n"
            f"💰 <b>តម្លៃចូល (Entry Price):</b> ${close_price:.2f}\n"
            f"🎯 <b>គោលដៅប្រាក់ចំណេញ (Take Profit):</b> ${tp_price:.2f} (-${tp_distance})\n"
            f"🛑 <b>ចំណុចកាត់ខាត (Stop Loss):</b> ${sl_price:.2f} (+${sl_distance})\n\n"
            f"🧠 <b>មូលហេតុ និងសញ្ញាបញ្ជាក់:</b>\n" + "\n".join([f"• {c}" for c in confluences]) + "\n\n"
            f"🛡 <b>តំបន់រារាំងសំខាន់ (Key Resistance):</b> ${swing_high:.2f}\n"
            f"⚠️ <i>ចំណាំ៖ ការជួញដូរមានហានិភ័យ សូមគ្រប់គ្រងដើមទុនឱ្យបានម៉ត់ចត់។</i>"
        )
        send_signal_telegram(msg)
        last_signal = f"SELL_{latest['timestamp']}"

# ------------------ MAIN RUNNER LOOP ------------------

if __name__ == "__main__":
    print("🤖 SMC Signal & Gold News Bot កំពុងដំណើរការ...")
    send_signal_telegram("🤖 <b>Bot វិភាគសញ្ញាមាស SMC ចាប់ផ្តើមដំណើរការ!</b>")
    send_news_telegram("📢 <b>ប្រព័ន្ធស្រង់ព័ត៌មានមាស ចាប់ផ្តើមដំណើរការ!</b>", "#", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "ប្រព័ន្ធ")

    cycle_count = 0

    while True:
        try:
            # 1. វិភាគ SMC Signal តម្លៃមាស (រត់រៀងរាល់ 30 វិនាទី)
            analyze_smc_risk_profiles()
            
            # 2. ឆែកមើលព័ត៌មានរៀងរាល់ 15 នាទីម្តង (30 cycles x 30s = 900s = 15mn)
            if cycle_count % 30 == 0:
                print("🔄 កំពុងទាញយកព័ត៌មានទីផ្សារមាសថ្មីៗ...")
                fetch_and_send_gold_news()
                
            cycle_count += 1
        except Exception as e:
            print(f"⚠️ មានបញ្ហាក្នុងការដំណើរការ Loop: {e}")

        time.sleep(30)
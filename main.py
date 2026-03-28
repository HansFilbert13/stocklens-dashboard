import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(
    page_title  = "Stock Volatility Dashboard",
    page_icon = "stocklens_logo.png",
    layout = "wide"
)

load_css("style.css")

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""
    <h1>📈 StockSense</h1>
    <p style='color:#8b949e; font-size:15px; margin-top:-12px; margin-bottom:24px; font-family: DM Sans, sans-serif;'>
        Analyze price movements, volatility & risk for any stock worldwide
    </p>
""", unsafe_allow_html=True)

@st.cache_data
def search_ticker(query):
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&limit=5"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        results = []
        for item in data.get('quotes', []):
            if item.get('quoteType') == 'EQUITY':  # only show stocks, not crypto/ETFs
                results.append({
                    'symbol': item.get('symbol', ''),
                    'name': item.get('longname') or item.get('shortname', ''),
                    'exchange': item.get('exchange', '')
                })
        return results
    except:
        return []

@st.cache_data(ttl=3600)
def load_data(ticker, start, end):
    df = yf.download(ticker, start=start, end=end)
    df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    
    info = yf.Ticker(ticker).info
    
    company_name = info.get('longName', ticker.upper())
    sector = info.get('sector', 'N/A')
    
    # Format market cap into readable form (e.g. $2.94T, $845B, $23M)
    raw_market_cap = info.get('marketCap', None)
    if raw_market_cap is None:
        market_cap = 'N/A'
    elif raw_market_cap >= 1_000_000_000_000:
        market_cap = f"${raw_market_cap / 1_000_000_000_000:.2f}T"
    elif raw_market_cap >= 1_000_000_000:
        market_cap = f"${raw_market_cap / 1_000_000_000:.2f}B"
    else:
        market_cap = f"${raw_market_cap / 1_000_000:.2f}M"
    
    
    recommendation = info.get('recommendationKey', None)
    rating_map = {
        'strong_buy': '✅ Buy',
        'buy':        '✅ Buy',
        'hold':       '⚖️ Neutral',
        'underperform': '❌ Don\'t Buy',
        'sell':       '❌ Don\'t Buy'
    }
    analyst_rating = rating_map.get(recommendation, '❓ No Rating')

    currency_code = info.get('currency', 'USD')
    currency_symbol_map = {
        'IDR': 'Rp ',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'SGD': 'S$',
        'HKD': 'HK$',
        'AUD': 'A$',
    }
    currency = currency_symbol_map.get(currency_code, currency_code + ' ')
    # IDR (and JPY) are high-value currencies — display without decimal places
    no_decimal_currencies = {'IDR', 'JPY'}
    use_no_decimal = currency_code in no_decimal_currencies

    ticker_obj = yf.Ticker(ticker)
    raw_news = ticker_obj.news[:5]  # only grab 5 most recent articles
    
    news = []
    for article in raw_news:
        content = article.get('content', {})
        news.append({
            'title': content.get('title', 'No title'),
            'summary': content.get('summary', ''),
            'url': content.get('canonicalUrl', {}).get('url', '#'),
            'source': content.get('provider', {}).get('displayName', 'Unknown'),
            'published': content.get('pubDate', '')
        })
    
    return df, company_name, sector, market_cap, analyst_rating, currency, use_no_decimal, news

st.sidebar.header("Settings")
st.sidebar.subheader("🔍 Search Stock")
st.sidebar.info("💡 For Indonesian stocks, you can directly type the ticker with .JK suffix — e.g. BBCA.JK, TLKM.JK")

search_query = st.sidebar.text_input(
    label="Search by name or ticker",
    value="Apple",
    help="Type a company name like 'Apple' or a ticker like 'AAPL'"
)

if search_query:
    results = search_ticker(search_query)
    
    if results:
        options = [f"{r['symbol']} — {r['name']}" for r in results]
        selected = st.sidebar.selectbox(
            label="Select company",
            options=options,
            help="Pick the company you were looking for"
        )
        ticker = selected.split(" — ")[0]
        
    else:
        st.sidebar.warning("No results found. Try a different search term.")
        ticker = "AAPL"  
else:
    ticker = "AAPL"

start_date = st.sidebar.date_input(
    label = "Start date",
    value=pd.Timestamp.today() - pd.DateOffset(years=2)
)

end_date = st.sidebar.date_input(
    label = "End date",
    value=pd.Timestamp.today()
)

window = st.sidebar.selectbox(
    label = "Volatility Window",
    options  = [30, 60, 90],
    index = 0,
    help = "Number of days to calculate rolling volatility"
)

st.markdown("---") 
st.sidebar.markdown("""
**💡 Tips**
- Try comparing different stocks by changing the ticker
- A higher volatility window (90d) gives a smoother, longer-term view
- A lower window (30d) reacts faster to recent market events
""")

df, company_name, sector, market_cap, analyst_rating, currency, use_no_decimal, news = load_data(ticker, start_date, end_date)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📰 Latest News")
if news:
    for article in news:
        st.sidebar.markdown(f"**[{article['title']}]({article['url']})**")
        st.sidebar.caption(f"🗞 {article['source']} · {article['published'][:10] if article['published'] else ''}")
        st.sidebar.markdown("---")
else:
    st.sidebar.caption("No recent news found.")



df['Daily Return'] = df['Close'].pct_change()
df['Volatility'] = df['Daily Return'].rolling(window).std() * (252 ** 0.5)

st.subheader(f"{ticker.upper()} - {company_name} - Overview")

info_col1, info_col2, info_col3 = st.columns(3)

info_col1.markdown(f"**🏭 Sector:** {sector}")
info_col2.markdown(f"**💰 Market Cap:** {market_cap}")
info_col3.markdown(f"**📊 Analyst Rating:** {analyst_rating}")

st.caption("Analyst rating is based on the consensus of Wall Street analysts covering this stock. It reflects whether professionals think the stock is worth buying at its current price.")
st.markdown("---")


col1, col2, col3, col4, col5, col6 = st.columns(6)

current_vol = float(df['Volatility'].iloc[-1])

if current_vol < 0.20:
    vol_status = "🟢 Low Risk"
elif current_vol < 0.40:
    vol_status = "🟡 Moderate Risk"
else:
    vol_status = "🔴 High Risk"

col1.metric(
    label="Latest Price",
    value=f"{currency}{float(df['Close'].iloc[-1]):,.0f}" if use_no_decimal else f"{currency}{float(df['Close'].iloc[-1]):.2f}",
    help="The closing price of the stock on the most recent trading day"
)

col2.metric(
    label="Daily Return",
    value=f"{float(df['Daily Return'].iloc[-1])*100:.2f}%",
    help="How much the stock price changed (%) compared to the previous day. Positive = price went up, Negative = price went down"
)

col3.metric(
    label="Current Volatility",
    value=f"{current_vol:.2%}",
    help=f"The {window}-day rolling volatility. Below 20% is calm, 20-40% is moderate, above 40% is high risk"
)
col3.markdown(f"{vol_status}")

col4.metric(
    label="Data Points",
    value=len(df),
    help="The total number of trading days loaded. Stock markets are closed on weekends and public holidays, so this is less than calendar days"
)

col5.metric(
    label="52-Week High",
    value=f"{currency}{float(df['Close'].max()):,.0f}" if use_no_decimal else f"{currency}{float(df['Close'].max()):.2f}",
    help="The highest closing price over the loaded date range"
)

col6.metric(
    label="52-Week Low",
    value=f"{currency}{float(df['Close'].min()):,.0f}" if use_no_decimal else f"{currency}{float(df['Close'].min()):.2f}",
    help="The lowest closing price over the loaded date range"
)

with st.expander("📖 New to this? Click here to understand what you're looking at"):
    st.markdown("""
    **Price Chart** — Shows the stock's closing price over time. A rising line means the stock has been going up in value.
    
    **Rolling Volatility** — Measures how much the stock price swings around. 
    Think of it like a "calmness score" in reverse — a higher number means the stock has been more unpredictable lately.
    - Below 20% → Calm and stable (e.g. utility companies)
    - 20–40% → Moderate movement (e.g. most large tech companies)
    - Above 50% → Very wild (e.g. meme stocks, crypto-linked stocks)
    
    **Volume** — How many shares were bought and sold each day. 
    A spike in volume usually means something significant happened (earnings report, news event, etc.)
    
    **Daily Return** — The percentage change in price from one day to the next. 
    If a stock was $100 yesterday and $103 today, the daily return is +3%.
    """)

chart_type = st.radio(
    label="Price chart type",
    options=["Line", "Candlestick"],
    horizontal=True,
    help="Candlestick shows Open/High/Low/Close per day — more detail than a simple line"
)

st.markdown("#### Compare with another stock (optional)")

compare_query = st.text_input(
    label="Search a second stock to compare volatility",
    value="",
    placeholder="e.g. Tesla, Microsoft, NVDA...",
    help="Leave empty to show only the main stock"
)

compare_ticker = None
if compare_query:
    compare_results = search_ticker(compare_query)
    if compare_results:
        compare_options = [f"{r['symbol']} — {r['name']}" for r in compare_results]
        compare_selected = st.selectbox(
            label="Select comparison stock",
            options=compare_options
        )
        compare_ticker = compare_selected.split(" — ")[0]

if compare_ticker:
    df_compare, compare_name, _, _, _, _, _ = load_data(compare_ticker, start_date, end_date)
    df_compare['Daily Return'] = df_compare['Close'].pct_change()
    df_compare['Volatility'] = df_compare['Daily Return'].rolling(window).std() * (252 ** 0.5)


download_df = df[['Date', 'Close', 'Daily Return', 'Volatility', 'Volume']].copy()
download_df.columns = ['Date', 'Close Price', 'Daily Return', f'{window}d Volatility', 'Volume']

csv = download_df.to_csv(index=False)

st.download_button(
    label="📥 Download Data as CSV",
    data=csv,
    file_name=f"{ticker}_volatility_data.csv",
    mime="text/csv",
    help="Download the full price and volatility data as a spreadsheet"
)

fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    subplot_titles=(
        "Price",
        f"{window}-Day Rolling Volatility",
        "Volume"
    ),
    row_heights=[0.5, 0.3, 0.2]
)

if chart_type == "Candlestick":
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price',
        increasing_line_color='#26A69A',
        decreasing_line_color='#EF5350'
    ), row=1, col=1)
else:
    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['Close'],
        name='Price',
        line=dict(color='#2196F3')
    ), row=1, col=1)


fig.add_trace(go.Scatter(
    x=df['Date'], y=df['Volatility'],
    name=f'{ticker} Volatility',
    line=dict(color='#FF9800')
), row=2, col=1)


if compare_ticker:
    fig.add_trace(go.Scatter(
        x=df_compare['Date'], y=df_compare['Volatility'],
        name=f'{compare_ticker} Volatility',
        line=dict(color='#E91E63', dash='dash')
    ), row=2, col=1)


fig.add_trace(go.Bar(
    x=df['Date'], y=df['Volume'],
    name='Volume',
    marker_color='#9E9E9E'
), row=3, col=1)

fig.update_layout(
    height=700,
    showlegend=True,
    hovermode='x unified',
    xaxis_rangeslider_visible=False,
    paper_bgcolor='#161b22',
    plot_bgcolor='#0d1117',
    font=dict(family='DM Sans', color='#8b949e'),
    xaxis=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    yaxis=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    xaxis2=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    yaxis2=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    xaxis3=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    yaxis3=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

if news:
    st.info(f"📰 **Latest headline:** {news[0]['title']} — scroll down to see all news")

st.subheader("📰 Latest News")

if news:
    for article in news:
        with st.container():
            col_news, col_link = st.columns([5, 1])
            
            with col_news:
                st.markdown(f"### {article['title']}")
                if article['summary']:
                    st.markdown(f"<p style='font-size:15px; color:#c9d1d9;'>{article['summary'][:180] + '...' if len(article['summary']) > 180 else article['summary']}</p>", unsafe_allow_html=True)
                st.caption(f"🗞 {article['source']}  ·  {article['published'][:10] if article['published'] else ''}")
            
            with col_link:
                st.link_button("Read →", article['url'])
            
            st.markdown("---")
else:
    st.caption("No recent news found for this stock.")

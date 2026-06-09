import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, "market_signals.txt")
BASE_URL = "https://fapi.binance.com"
# BASE_URL = "https://testnet.binancefuture.com"
MIN_VOLUME = 100_000_000
INTERVAL = "30m"
LIMIT = 50
# CHANGE_THRESHOLD = 1.0
IMPULSE_CANDLES = 3
COMPRESSION_CANDLES = 2
#2
WATCH_COMPRESSION_MAX  = 2.0
#0.7
# READY_COMPRESSION_MAX = 0.55
#0.4
WATCH_PULLBACK_MAX  = 2.0
#0.8
# READY_PULLBACK_MAX = 0.6
#0.35
READY_COMPRESSION_MAX = 1.2
READY_PULLBACK_MAX = 1.5
MIN_SCORE = 1.0
#1

MAX_PAIRS = 150
CACHE_LIFETIME = 120
KLINES_CACHE_TTL = 60
SIGNAL_COOLDOWN = 600 


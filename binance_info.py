import requests
import time
import threading
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from server_time import get_timestamp
from dataclasses import dataclass
from trade_mode import get_open_orders, get_open_position_amt, set_leverage, normalize_quantity, adjust_price_precision, get_mark_price, place_market_order, place_conditional_order, get_futures_usdt_balance, calculate_sl_tp_from_deposit_risk
from db_file import cleanup_expired_signals, get_pending_signals, update_signal_status, save_pending_signal
from dotenv import load_dotenv
from config import (
    MIN_SCORE,
    IMPULSE_CANDLES,
    WATCH_COMPRESSION_MAX,
    READY_COMPRESSION_MAX,
    WATCH_PULLBACK_MAX,
    READY_PULLBACK_MAX,
    COMPRESSION_CANDLES,
    BASE_URL,
    INTERVAL,
    LIMIT,
    MIN_VOLUME,
    MAX_PAIRS,
    CACHE_LIFETIME,
    KLINES_CACHE_TTL,
    SIGNAL_COOLDOWN,
    FILE_PATH
)


load_dotenv()

ACCOUNTS = [
    {
        "name": "Kseniia",
        "api_key": os.getenv("API_KEY_1"),
        "secret_key": os.getenv("SECRET_KEY_1")
    }
    # {
    #     "name": "Maxim",
    #     "api_key": os.getenv("API_KEY_2"),
    #     "secret_key": os.getenv("SECRET_KEY_2")
    # }
]


logger = logging.getLogger(__name__)

cached_pairs = []
pairs_last_update = 0

last_sent_signals = {}   
symbol_state = {}
klines_cache = {}
klines_cache_time = {}


@dataclass
class Signal:
    symbol: str
    direction: str
    impulse: float
    compression: float
    pullback: float
    score: float
    sl_distance: float
    stop_loss: float
    threshold: float | None = None


def get_usdt_pairs():

    global cached_pairs, pairs_last_update

    now = time.time()

    if cached_pairs and now - pairs_last_update < CACHE_LIFETIME:
        return cached_pairs

    try:
        url = f"{BASE_URL}/fapi/v1/ticker/24hr"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            return cached_pairs

        data = r.json()

        pairs = []

        for item in data:
            try:
                symbol = item["symbol"]
                volume = float(item.get("quoteVolume", 0))

                if symbol.endswith("USDT") and volume >= MIN_VOLUME:
                    pairs.append((symbol, volume))
                    # logger.info(f"Symbol: {symbol}")

            except Exception:
                logger.exception(f"Ошибка check_pair {symbol}")
                continue

        pairs.sort(key=lambda x: x[1], reverse=True)
        pairs = [p[0] for p in pairs[:MAX_PAIRS]]

        cached_pairs = pairs
        pairs_last_update = now

        logger.info(f"Пар найдено: {len(pairs)}")
        return pairs

    except Exception:
        logger.exception("Ошибка получения списка пар")
        return cached_pairs


def get_klines(symbol):

    now = time.time()

    if len(klines_cache) > 200:
        klines_cache.clear()
        klines_cache_time.clear()
    
    if symbol in klines_cache:
        if now - klines_cache_time.get(symbol, 0) < KLINES_CACHE_TTL:
            return klines_cache[symbol]
        
    try:
        time.sleep(0.05)
        
        url = f"{BASE_URL}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": INTERVAL,
            "limit": LIMIT
        }

        r = requests.get(url, params=params, timeout=8)

        if r.status_code != 200:
            logger.warning(f"Klines error {symbol}: {r.text}")
            return None

        data = r.json()

        klines_cache[symbol] = data
        klines_cache_time[symbol] = now

        return data

    except Exception:
        logger.exception(f"Ошибка get_klines {symbol}")
        return None
    

def get_atr(highs, lows, closes, period=14):
  
    tr_values = []

    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    if len(tr_values) < period:
        return None

    return sum(tr_values[-period:]) / period


def atr_percent(atr, price):
    return (atr / price) * 100


def dynamic_threshold(atr_pct):
    return atr_pct * 2.0   


def check_pair(symbol):

    try:
        klines = get_klines(symbol)

        if klines is None:
            logger.warning(f"{symbol}: klines is None")
            return None

        if len(klines) < (IMPULSE_CANDLES + COMPRESSION_CANDLES + 10):
            logger.info(f"Symbol: {symbol},  impulse: {len(klines)}")
            return None
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]

        now = time.time()

        prev = symbol_state.get(symbol, {
            "state" : "NONE",
            "last_update" : 0
        })

        impulse_open = closes[-(IMPULSE_CANDLES + COMPRESSION_CANDLES + 1)]
        impulse_close = closes[-(COMPRESSION_CANDLES + 1)]

        impulse = (
            (impulse_close - impulse_open)
            / impulse_open
        ) * 100

        atr = get_atr(highs, lows, closes, period=14)

        if not atr:
            print(f"not atr {symbol}")
            return None

        price = closes[-1]

        atr_pct = (atr / price) * 100

        threshold = dynamic_threshold(atr_pct)

        if abs(impulse) < threshold:
            # logger.info(f"Symbol: {symbol},  abs(impulse): {abs(impulse)}, threshold: {threshold}")
            return None
            
        
        impulse_strength = abs(impulse) / atr_pct

        if impulse_strength < 2.0:
            logger.info(f"Symbol: {symbol},  impulse_strength: {impulse_strength}")
            return None
        
        recent_high = max(highs[-COMPRESSION_CANDLES:-1])
        recent_low =  min(lows[-COMPRESSION_CANDLES:-1])
        # print(f"Symbol: {symbol}; recent_high: {recent_high}, recent_low: {recent_low}")

        range_percent = (
            (recent_high - recent_low)
            / recent_low
        ) * 100

        compression_ratio = range_percent / atr_pct

        current_price = closes[-1]

        pullback = (
            abs(current_price - impulse_close)
            / impulse_close
        ) * 100

        pullback_ratio = pullback / atr_pct

        state = prev["state"]

        if (
            compression_ratio > WATCH_COMPRESSION_MAX
            or pullback_ratio > WATCH_PULLBACK_MAX
        ):
            state = "NONE"

        elif (
            compression_ratio < READY_COMPRESSION_MAX
            and pullback_ratio < READY_PULLBACK_MAX
        ):
            state = "READY"

        else:
            state = "BUILDING"

        breakout_distance = (
            abs(current_price - recent_high)
            / recent_high
        ) * 100

        breakout = breakout_distance < (atr_pct * 0.18)

        score = (
            impulse_strength
            * (1 / (1 + compression_ratio))
            * (1 / (1 + pullback_ratio))
        )
        
        
        symbol_state[symbol] = {
            "state" : state,
            "impulse" : impulse,
            "compression" : compression_ratio,
            "pullback" : pullback_ratio,
            "score" : score,
            "time" : now
            }
        
        if state != "READY":
            return None
        
        if score < MIN_SCORE:
            logger.info(f"Symbol: {symbol},  score: {score}")
            return None
        
        if not breakout:
            logger.info(f"Symbol: {symbol},  breakout: {breakout}")
            return None

        
        direction = (
            "LONG"
            if impulse > 0
            else "SHORT"
        )

        stop_loss, sl_distance = calculate_sl_by_structure(entry_price=price,
            highs=highs, lows=lows,
            direction=direction,
            atr=atr
        )

        return Signal(
            symbol=symbol,
            direction=direction,
            impulse=round(impulse, 2),
            compression=round(compression_ratio, 2),
            pullback=round(pullback_ratio, 2),
            score=round(score, 2),
            sl_distance=sl_distance,
            stop_loss=stop_loss,
            threshold=threshold
        )
            
    
    except Exception:
        logger.exception(f"Ошибка check_pair {symbol}")
        return None


def scan_market():

    pairs = get_usdt_pairs()

    results = []

    max_workers = min(5, len(pairs)) if pairs else 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
            outputs = list(executor.map(check_pair, pairs))

    for symbol, result in zip(pairs, outputs):

        if result is None:
            continue

        results.append(result)

    results.sort(key=lambda s: s.score, reverse=True)

    return results[:1]


def can_send_signal(symbol: str):

    global last_sent_signals

    now = time.time()

    last_sent_signals = {
        s: t for s, t in last_sent_signals.items()
        if now - t < SIGNAL_COOLDOWN
    }

    last_time = last_sent_signals.get(symbol)

    if last_time:
        return False

    last_sent_signals[symbol] = now
    return True


def write_signal(signal: Signal):

    text = (
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"{signal.symbol} | "
        f"{signal.direction} | "
        f"Impulse: {signal.impulse}% | "
        f"Compression: {signal.compression}% | "
        f"Pullback: {signal.pullback}% | "
        f"Score: {signal.score}% |"
        f"Threshold: {signal.threshold}% |"
        f"SL: {signal.stop_loss}\n "
    )

    with open(FILE_PATH, "a", encoding="utf-8") as f:
        f.write(text)
 
scanner_active = False

def scanner_loop():

    while scanner_active:

        hour = time.localtime().tm_hour


        if hour >= 22 or hour < 2:
            logger.info(f"It is night. Stop scan.")
            time.sleep(600)
            continue


        try:
            signals = scan_market()

        except Exception:
            logger.exception("Ошибка scan_market")
            time.sleep(10)
            continue


        for signal in signals:

            if not scanner_active:
                return

            if not can_send_signal(signal.symbol):
                continue

            write_signal(signal)
        
            for account in ACCOUNTS:
                try:

                    open_orders = get_open_orders(account["api_key"], account["secret_key"], signal.symbol)

                    position_amt = get_open_position_amt(account["api_key"], account["secret_key"],signal.symbol)

                    if position_amt > 0:
                        print(f"Symbol: {signal.symbol}. Pos open.")
                        continue

                    if open_orders:
                        print(f" Skip {signal.symbol}. Open")
                        continue

                    price = get_mark_price(signal.symbol)
                    set_leverage(account["api_key"], account["secret_key"], signal.symbol, 10)

                    thr_prc = signal.threshold * 0.95
                    
                    activate_distance = price * thr_prc / 100

                    if signal.direction == "LONG":
                        activate_price = price - activate_distance
                        side = "BUY"
                    else:
                        activate_price = price + activate_distance
                        side = "SELL"

                    activate_price = float(adjust_price_precision(signal.symbol, activate_price))

                    deposit = get_futures_usdt_balance(account["api_key"], account["secret_key"])
                    sl_tp_calc = calculate_sl_tp_from_deposit_risk(
                        entry_price=activate_price,
                        direction=signal.direction,
                        sl_distance=signal.sl_distance,
                        deposit_usdt=deposit
                    )

                    qty = sl_tp_calc["qty"]
                    qty_str = normalize_quantity(signal.symbol, qty)

                    saved = save_pending_signal(
                        account_name=account["name"],
                        symbol=signal.symbol,
                        side=side,
                        qty=float(qty_str),
                        activate_price=activate_price,
                        sl=sl_tp_calc["stop_loss"],
                        tp=sl_tp_calc["take_profit"]
                    )

                    if saved:
                        print(
                            f"📌 Сигнал {signal.symbol} "
                            f"сохранён в мониторинг"
                        )
                    else:
                        print(
                            f"⚠️ Уже есть PENDING "
                            f"для {signal.symbol}"
                        )

                except Exception:
                    logger.exception(f"Account {account["name"]} error")


        time.sleep(180)


def start_scanner():

    global scanner_active

    if scanner_active:
        print("Сканер уже работает")
        return

    scanner_active = True

    threading.Thread(
        target=monitor_pending_signals, 
        daemon=True
        ).start()

    threading.Thread(
        target=scanner_loop,
        daemon=True
    ).start()

    print("✅ Сканер запущен")


def stop_scanner():

    global scanner_active

    scanner_active = False

    print("⏹ Сканер остановлен")


def reset_scanner_cache():

    global cached_pairs, pairs_last_update

    cached_pairs = []
    pairs_last_update = 0
    logger.info("Кэш сканера полностью сброшен")


def calculate_sl_by_structure(entry_price, highs, lows, direction, atr, buffer_mult= 1.0):

    recent_high = max(highs[-COMPRESSION_CANDLES:-1])
    recent_low = min(lows[-COMPRESSION_CANDLES:-1])

    buffer = atr * buffer_mult

    sl_min_distance = atr * 1.0
    sl_max_distance = atr * 3.0

    if direction == "LONG":
        sl = recent_low - buffer
        sl_distance = entry_price - sl
    else:
        sl = recent_high + buffer
        sl_distance = sl - entry_price

    sl_distance = max(sl_min_distance, sl_distance)
    sl_distance = min(sl_max_distance, sl_distance)

    if direction == "LONG":
        stop_loss = entry_price - sl_distance
    else:
        stop_loss = entry_price + sl_distance

    return stop_loss, sl_distance


def monitor_pending_signals():

    global scanner_active
    
    while scanner_active:  
        try:
            if time.time() % 300 < 30:
                cleanup_expired_signals()
            pendings = get_pending_signals()
            
            for row in pendings:
                sig_id = row[0]
                account_name = row[1]
                symbol = row[2]
                side = row[3]
                qty = row[4]
                activate_price = row[5]
                sl = row[6]
                tp = row[7]
                
                # Находим аккаунт
                account = next((a for a in ACCOUNTS if a["name"] == account_name), None)
                if not account:
                    update_signal_status(sig_id, "ERROR")
                    continue
                
                current_price = get_mark_price(symbol)
                
                should_activate = False
                if side == "BUY":   # LONG
                    if current_price <= activate_price:
                        should_activate = True
                else:  # SHORT
                    if current_price >= activate_price:
                        should_activate = True
                
                if should_activate:
                    print(f"✅ Активация сигнала {symbol} {side} по цене {current_price}")
                    
                    # Открываем маркет
                    result = place_market_order(
                        account["api_key"], account["secret_key"], 
                        symbol, side, qty
                    )
                    
                    if result:
                        opposite = "SELL" if side == "BUY" else "BUY"
                        sl_params = {
                            "symbol": symbol,
                            "side": opposite,
                            "type": "STOP_MARKET",
                            "algoType": "CONDITIONAL",           
                            "triggerPrice": adjust_price_precision(symbol, sl),
                            "closePosition": "true",
                            "workingType": "MARK_PRICE",
                            "timestamp": get_timestamp(),
                            "recvWindow": 10000
                        }

                        tp_params = {
                            "symbol": symbol,
                            "side": opposite,
                            "type": "TAKE_PROFIT_MARKET",
                            "algoType": "CONDITIONAL",           
                            "triggerPrice": adjust_price_precision(symbol, tp),
                            "closePosition": "true",
                            "workingType": "MARK_PRICE",
                            "timestamp": get_timestamp(),
                            "recvWindow": 10000
                        }
                        
                        place_conditional_order(account["api_key"], account["secret_key"], sl_params)
                        place_conditional_order(account["api_key"], account["secret_key"], tp_params)
                        
                        update_signal_status(sig_id, "DONE")
                    else:
                        update_signal_status(sig_id, "ERROR")
                        
        except Exception as e:
            logger.exception("Ошибка мониторинга pending")
        
        time.sleep(30)  


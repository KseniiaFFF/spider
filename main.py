import time
import threading

from binance_info import start_scanner
from log_settings import set
from db_file import init_db
from server_time import sync_loop, sync_time

init_db()
set()
sync_time()

threading.Thread(
    target=sync_loop,
    daemon=True
).start()

start_scanner()

while True:
    time.sleep(1)
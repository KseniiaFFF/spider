import time

from binance_info import start_scanner
from log_settings import set
from db_file import init_db

init_db()
set()
start_scanner()

while True:
    time.sleep(1)
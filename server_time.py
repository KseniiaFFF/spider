import time
import logging
import requests

from config import BASE_URL

logger = logging.getLogger(__name__)

def get_server_time(base_url=BASE_URL):
    try:
        url = f"{base_url}/fapi/v1/time"
        response = requests.get(url, timeout=5)
        return response.json()["serverTime"]
    except Exception as e:
        logger.exception(f'Time sync error {e}')
        return int(time.time() * 1000)
    

time_offset = 0

def sync_time():
    global time_offset
    server_time = get_server_time()
    local_time = int(time.time() * 1000)
    time_offset = server_time - local_time


def get_timestamp():
    return int(time.time() * 1000) + time_offset
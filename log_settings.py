import logging

#базовые параметры для логов
def set():
    logging.basicConfig(filename = 'log_market_bot_on_trade.txt',
                    level=logging.INFO,
                    encoding='utf-8',
                    format='%(asctime)s - '
                    '%(name)s - '
                    '%(levelname)s - '
                    '%(message)s')
    
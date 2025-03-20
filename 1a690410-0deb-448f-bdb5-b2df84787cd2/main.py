from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from datetime import datetime

class TradingStrategy(Strategy):
    def __init__(self):
        # Assuming 'WTI' is the symbol for trading crude oil, replace with actual if different
        self.ticker = "WTI"

    @property
    def assets(self):
        # Trading strategy for a single asset: crude oil
        return [self.ticker]

    @property
    def interval(self):
        # Daily strategy, adjust if a finer time resolution is required 
        # (though note, execution based on specific 'morning' or 'evening' times will need custom logic outside this framework)
        return "1day"

    def run(self, data):
        # Fetch current date and time
        now = datetime.now()
        
        # Assuming market open at 09:30 and close at 16:00, these times will need adjustment to match the trading location's times
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        allocation = 0

        # If current time is close to market open, allocate 100% to buy
        if now <= market_open:
            log("Allocating 100% to buy crude oil in the morning.")
            allocation = 1
        # If current time is close to market close, allocate 0% indicating to sell  
        elif now >= market_close:
            log("Reducing allocation to 0% to indicate selling crude oil in the evening.")
            allocation = 0

        return TargetAllocation({self.ticker: allocation})
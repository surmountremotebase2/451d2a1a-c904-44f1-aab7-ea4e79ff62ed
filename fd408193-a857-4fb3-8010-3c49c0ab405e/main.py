from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, ATR

class GoldOvernightStrategy(Strategy):
    def __init__(self):
        # Core strategy tickers
        self.tickers = ["GLD"]
        
        # Position size - we'll use 95% of capital for overnight positions
        self.position_size = 0.95
        
        # Trading state
        self.in_position = False
        self.day_count = 0
        
        # For performance tracking
        self.wins = 0
        self.losses = 0
        self.last_entry_price = None

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    def run(self, data):
        # Increment day counter
        self.day_count += 1
        
        # Get price data
        ohlcv = data["ohlcv"]
        current_data = ohlcv[-1]["GLD"]
        current_close = current_data["close"]
        current_open = current_data["open"]
        
        # Default allocation (no position)
        allocation = {ticker: 0 for ticker in self.tickers}
        
        # Simple alternating strategy:
        # - Even days: Buy at close
        # - Odd days: Sell at open
        
        # If we're in a position, sell
        if self.in_position:
            # Track performance if we have entry price
            if self.last_entry_price is not None:
                pnl = (current_open - self.last_entry_price) / self.last_entry_price
                if pnl > 0:
                    self.wins += 1
                else:
                    self.losses += 1
                total_trades = self.wins + self.losses
                win_rate = self.wins / total_trades if total_trades > 0 else 0
            
            # Exit the position
            allocation["GLD"] = 0
            self.in_position = False
            
        # If we're not in a position, buy
        else:
            # Enter a new position
            allocation["GLD"] = self.position_size
            self.in_position = True
            self.last_entry_price = current_close
        
        return TargetAllocation(allocation)

# This is the class that will be instantiated for the strategy
class TradingStrategy(GoldOvernightStrategy):
    pass
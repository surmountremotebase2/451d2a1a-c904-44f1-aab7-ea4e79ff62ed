from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, ATR

class GoldOvernightStrategy(Strategy):
    def __init__(self):
        # Core strategy tickers
        self.tickers = ["GLD"]
        
        # Position size
        self.position_size = 0.95
        
        # Technical parameters
        self.atr_period = 14
        self.rsi_period = 14
        self.sma_short = 50
        self.sma_long = 200
        
        # Trading state
        self.in_position = False
        self.day_counter = 0
        self.trade_day = True  # Assume we trade every day by default

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    def run(self, data):
        # Create default allocation dictionary
        allocation = {ticker: 0 for ticker in self.tickers}
        
        # Get price data for GLD
        ohlcv_data = data["ohlcv"]
        
        # Track backtest day
        self.day_counter += 1
        
        # Print daily information for debugging
        current_price = ohlcv_data[-1]["GLD"]["close"]
        print(f"Day {self.day_counter}: GLD Price = ${current_price:.2f}, In Position: {self.in_position}")
        
        # Calculate some basic indicators (for risk management)
        rsi = RSI("GLD", ohlcv_data, self.rsi_period)[-1]
        sma_long_value = SMA("GLD", ohlcv_data, self.sma_long)[-1]
        
        # If we're in a position, sell at the day's open
        if self.in_position:
            print(f"SELLING GLD at open: ${ohlcv_data[-1]['GLD']['open']:.2f}")
            allocation["GLD"] = 0
            self.in_position = False
            return TargetAllocation(allocation)
        
        # Check basic risk filters (only filter extreme conditions)
        self.trade_day = True
        
        # Extreme RSI filter (very overbought)
        if rsi > 85:
            print(f"Skipping trade: RSI too high ({rsi:.1f})")
            self.trade_day = False
            
        # Extreme downtrend filter (well below 200-day SMA)
        if current_price < sma_long_value * 0.8:
            print(f"Skipping trade: Price too far below 200-day SMA")
            self.trade_day = False
        
        # If not in a position, buy at the close for the overnight hold
        if not self.in_position and self.trade_day:
            print(f"BUYING GLD at close: ${current_price:.2f}")
            allocation["GLD"] = self.position_size
            self.in_position = True
                
        return TargetAllocation(allocation)

# This is the class that will be instantiated for the strategy
class TradingStrategy(GoldOvernightStrategy):
    pass
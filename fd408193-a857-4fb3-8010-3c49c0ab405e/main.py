from surmount.base_class import Strategy, TargetAllocation
from surmount.data import Asset
from surmount.technical_indicators import ATR, SMA
from datetime import datetime
import pytz

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["GLD"]
        self.entry_time = "15:55:00"
        self.exit_time = "09:35:00"
        self.timezone = pytz.timezone("America/New_York")
        self.max_position_size = 0.20  # 20% of the portfolio
        self.atr_length = 10
        self.sma_short_length = 50
        self.sma_long_length = 200

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return [
            Asset("GLD"),
            Asset("VIX"),  # For the VIX volatility filter
            Asset("DXY"),  # For the US Dollar Index as a gold-specific indicator
        ]

    def run(self, data):
        allocation = {}
        now = datetime.now(self.timezone).strftime("%H:%M:%S")
        current_price = data["ohlcv"][-1]["GLD"]["close"]
        
        # ATR and MA calculations for volatility and trend filters
        atr = ATR("GLD", data["ohlcv"], self.atr_length)
        sma_short = SMA("GLD", data["ohlcv"], self.sma_short_length)
        sma_long = SMA("GLD", data["ohlcv"], self.sma_long_length)
        
        # Decision making based on time criteria
        if now >= self.entry_time:
            allocation = self.entry_logic(current_price, atr, sma_short, sma_long, data)
        elif now >= self.exit_time:
            allocation = self.exit_logic()
        
        return TargetAllocation(allocation)

    def entry_logic(self, current_price, atr, sma_short, sma_long, data):
        allocation = {}
        position_size = self.max_position_size
        
        # Adjust position size based on volatility
        if atr[-1] > SMA("GLD", data["ohlcv"], 20)[-1]:
            position_size *= 0.75  # Reduce position size by 25%
        if atr[-1] > SMA("GLD", data["ohlcv"], 20)[-1] * 2:
            position_size *= 0.50  # Reduce position size by 50%
        
        # Trend filter adjustment
        if current_price > sma_short[-1] and sma_short[-1] > sma_long[-1]:
            pass  # Full position
        elif sma_short[-1] > sma_long[-1]:
            position_size *= 0.75  # 75% position size
        else:
            position_size *= 0.50  # 50% position size
        
        # VIX volatility filter adjustment
        vix_close = data["ohlcv"][-1]["VIX"]["close"]
        if vix_close > 30:
            position_size *= 0.75
        if vix_close > 40:
            position_size *= 0.50

        # Gold-specific indicators (DXY)
        dxy_close = data["ohlcv"][-1]["DXY"]["close"]
        if dxy_close > 0.5:
            position_size *= 0.75  # Reduce if DXY is up more than 0.5%

        allocation["GLD"] = position_size
        return allocation

    def exit_logic(self):
        # Exit the position by setting allocation to 0%
        return {"GLD": 0}
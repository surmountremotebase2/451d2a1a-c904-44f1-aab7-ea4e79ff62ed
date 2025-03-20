from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, ATR, MACD, BB
from surmount.data import BroadUSDollarIndex, StLouisFinancialStressIndex
from datetime import datetime, timedelta
import pytz

class GoldOvernightStrategy(Strategy):
    def __init__(self):
        # Core strategy tickers
        self.tickers = ["GLD"]
        
        # Risk management parameters
        self.base_position_size = 0.95  # 95% allocation when active
        self.catastrophic_stop_pct = 0.05  # 5% catastrophic stop loss
        self.morning_gap_threshold = 0.02  # 2% gap threshold
        
        # Technical analysis parameters
        self.atr_period = 14
        self.rsi_period = 14
        self.sma_short = 50
        self.sma_long = 200
        self.volatility_lookback = 20
        
        # Market condition filters
        self.dollar_strength_threshold = 0.5
        
        # Trading state
        self.in_position = False

    @property
    def interval(self):
        """Define the data interval needed"""
        return "1day"  # Using daily data

    @property
    def assets(self):
        """Define the assets needed for the strategy"""
        return self.tickers

    @property
    def data(self):
        """Define additional data sources needed"""
        return [
            BroadUSDollarIndex(),  # Dollar index (inversely correlated with gold)
            StLouisFinancialStressIndex(),  # Financial stress indicator
        ]

    def run(self, data):
        """
        Main strategy execution logic
        """
        # Initialize empty allocation dictionary
        allocation = {ticker: 0 for ticker in self.tickers}
        
        # Get latest price data for GLD
        ohlcv_data = data["ohlcv"]
        latest_close = ohlcv_data[-1]["GLD"]["close"]
        
        # Calculate technical indicators
        atr_values = ATR("GLD", ohlcv_data, self.atr_period)
        rsi_values = RSI("GLD", ohlcv_data, self.rsi_period)
        sma_short_values = SMA("GLD", ohlcv_data, self.sma_short)
        sma_long_values = SMA("GLD", ohlcv_data, self.sma_long)
        
        # Calculate average ATR for volatility scaling
        avg_atr = sum(atr_values[-self.volatility_lookback:]) / self.volatility_lookback
        current_atr = atr_values[-1]
        
        # Get macroeconomic indicators
        try:
            dollar_index = data[("broad_us_dollar_index")][-1]["value"]
            financial_stress = data[("stlouis_financial_stress_index")][-1]["value"]
        except (KeyError, IndexError):
            # Handle missing data gracefully
            dollar_index = None
            financial_stress = None
        
        # Decision making based on position state
        # Since we can't use intraday data, we'll implement a modified overnight strategy
        # We'll buy at the close of one day and sell at the open of the next day
        
        # Get current date/time to determine if it's a new day
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Check if we have previous date in our data
        if len(ohlcv_data) > 1:
            previous_date = datetime.fromtimestamp(ohlcv_data[-2]["GLD"]["time"]).strftime("%Y-%m-%d")
            new_day = current_date != previous_date
        else:
            new_day = True
            
        # Entry logic (buy at close)
        if not self.in_position:
            # Apply position sizing based on market conditions
            position_size = self._calculate_position_size(
                self.base_position_size,
                latest_close,
                current_atr,
                avg_atr,
                rsi_values[-1],
                sma_short_values[-1],
                sma_long_values[-1],
                dollar_index,
                financial_stress
            )
            
            # Check if we should enter the trade
            if self._should_enter(latest_close, sma_short_values[-1], sma_long_values[-1], rsi_values[-1]):
                allocation["GLD"] = position_size
                self.in_position = True
                print(f"ENTRY: Buying GLD at ${latest_close:.2f}")
        
        # Exit logic (sell at open of next day)
        elif self.in_position and new_day:
            # Exit the position completely
            allocation["GLD"] = 0
            self.in_position = False
            
            # Calculate P&L if we have enough data
            if len(ohlcv_data) > 1:
                entry_price = ohlcv_data[-2]["GLD"]["close"]  # Previous day's close
                exit_price = ohlcv_data[-1]["GLD"]["open"]    # Current day's open
                pnl_pct = (exit_price - entry_price) / entry_price
                print(f"EXIT: Selling GLD at ${exit_price:.2f}, P&L: {pnl_pct:.2%}")
        
        # Return the target allocation
        return TargetAllocation(allocation)
    
    def _calculate_position_size(self, base_size, price, current_atr, avg_atr, 
                                rsi, sma_short, sma_long, dollar_idx, financial_stress):
        """
        Calculate the position size based on various factors and risk management rules
        """
        # Start with the base position size
        position_size = base_size
        
        # 1. Adjust for volatility
        volatility_ratio = current_atr / avg_atr
        if volatility_ratio > 1.5:
            position_size *= 0.75  # Reduce by 25% for high volatility
        if volatility_ratio > 2.0:
            position_size *= 0.5   # Reduce by 50% for extreme volatility
        
        # 2. Adjust for trend strength
        if price < sma_long:
            position_size *= 0.8  # Reduce by 20% if below 200 SMA
        
        # 3. Adjust for dollar strength (inversely correlated with gold)
        if dollar_idx is not None and dollar_idx > self.dollar_strength_threshold:
            position_size *= 0.9  # Reduce by 10% if dollar is strong
        
        # 4. Adjust for financial stress (directly correlated with gold as safe haven)
        if financial_stress is not None and financial_stress > 0.5:
            position_size *= 1.1  # Increase by 10% during financial stress
            position_size = min(position_size, self.base_position_size)  # Cap at base size
        
        # 5. Adjust for extreme RSI readings
        if rsi > 80:
            position_size *= 0.8  # Reduce by 20% if RSI is overbought
        elif rsi < 20:
            position_size *= 1.1  # Increase by 10% if RSI is oversold
            position_size = min(position_size, self.base_position_size)  # Cap at base size
        
        return position_size
    
    def _should_enter(self, price, sma_short, sma_long, rsi):
        """
        Determine if we should enter the trade based on market conditions
        """
        # Skip trade on extreme RSI readings
        if rsi > 85 or rsi < 15:
            return False
        
        # Skip trade if price is far below long-term trend
        if price < sma_long * 0.85:
            return False
        
        return True

# This is the class that will be instantiated for the strategy
class TradingStrategy(GoldOvernightStrategy):
    pass
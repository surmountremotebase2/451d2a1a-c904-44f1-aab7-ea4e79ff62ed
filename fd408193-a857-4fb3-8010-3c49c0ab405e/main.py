from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, ATR, MACD, BB
from surmount.data import CapacityUtilizationRate, StLouisFinancialStressIndex
from surmount.data import BroadUSDollarIndex, M2MoneyStock
from datetime import datetime, timedelta
import pytz
class GoldOvernightStrategy(Strategy):
def init(self):
# Core strategy tickers
self.tickers = ["GLD"]

# Trading timing parameters (Eastern Time)
    self.entry_time = "15:55"  # 5 minutes before market close
    self.exit_time = "09:35"   # 5 minutes after market open
    self.timezone = pytz.timezone("America/New_York")
    
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
    self.vix_threshold = 30
    self.extreme_vix_threshold = 40
    self.dollar_strength_threshold = 0.5

@property
def interval(self):
    """Define the data interval needed"""
    return "5minute"  # Using 5-minute data for precise entry/exit

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
        CapacityUtilizationRate(),  # Economic indicator
        M2MoneyStock()  # Monetary supply (positively correlated with gold)
    ]

def run(self, data):
    """
    Main strategy execution logic
    """
    # Initialize empty allocation dictionary
    allocation = {ticker: 0 for ticker in self.tickers}
    
    # Get current datetime in Eastern Time
    now = datetime.now(self.timezone)
    current_time = now.strftime("%H:%M")
    
    # Get latest price data for GLD
    ohlcv_data = data["ohlcv"]
    latest_close = ohlcv_data[-1]["GLD"]["close"]
    
    # Calculate technical indicators
    atr_values = ATR("GLD", ohlcv_data, self.atr_period)
    rsi_values = RSI("GLD", ohlcv_data, self.rsi_period)
    sma_short_values = SMA("GLD", ohlcv_data, self.sma_short)
    sma_long_values = SMA("GLD", ohlcv_data, self.sma_long)
    
    # Get bollinger bands
    bb = BB("GLD", ohlcv_data, 20, 2)
    
    # Calculate average ATR for volatility scaling
    avg_atr = sum(atr_values[-self.volatility_lookback:]) / self.volatility_lookback
    current_atr = atr_values[-1]
    
    # Get macroeconomic indicators
    try:
        dollar_index = data[("broad_us_dollar_index")][-1]["value"]
        financial_stress = data[("stlouis_financial_stress_index")][-1]["value"]
        money_supply = data[("m2_money_stock")][-1]["value"]
    except (KeyError, IndexError):
        # Handle missing data gracefully
        dollar_index = None
        financial_stress = None
        money_supply = None
    
    # Decision making based on time of day
    position_size = self.base_position_size
    
    # ENTRY LOGIC - 5 minutes before market close (3:55 PM ET)
    if current_time == self.entry_time:
        # Apply position sizing based on market conditions
        position_size = self._calculate_position_size(
            position_size,
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
        
    # EXIT LOGIC - 5 minutes after market open (9:35 AM ET)
    elif current_time == self.exit_time:
        # Exit the position completely
        allocation["GLD"] = 0
        
        # Log the trade metrics for analysis
        entry_price = ohlcv_data[-2]["GLD"]["close"]  # Previous day's close
        exit_price = latest_close
        pnl_pct = (exit_price - entry_price) / entry_price
        print(f"Trade completed: Entry: ${entry_price:.2f}, Exit: ${exit_price:.2f}, P&L: {pnl_pct:.2%}")
    
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
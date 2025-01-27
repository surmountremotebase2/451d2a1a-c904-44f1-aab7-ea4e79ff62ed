from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.technical_indicators import SMA
from datetime import datetime

class TradingStrategy(Strategy):
    def __init__(self):
        # Using GLD as a proxy for gold trading
        self.tickers = ["GLD"]
        self.data_list = []
        
        # Strategy parameters
        self.max_positions = 17  # Initial + 16 additional
        self.initial_allocation = 0.01  # Equivalent to 0.01 lot
        self.tp_distance = 0.8  # Take profit distance
        self.sl_distance = 20.0  # Stop loss distance
        self.grid_step = 1.0  # Price difference for new position
        self.adjustment_threshold = 6  # Positions threshold for TP adjustment
        self.tp_adjustment_percent = 0.70  # 70% for TP adjustment
        
        # Position tracking
        self.active_positions = []
        self.last_check_prices = {}

    @property
    def interval(self):
        return "1day"  # Using daily interval

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def is_time_to_check(self, date_str):
        """Check if it's 5 AM or 9 AM"""
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return dt.hour in [5, 9]

    def calculate_trend(self, price_5am, price_9am):
        """Determine market trend"""
        return "bullish" if price_9am > price_5am else "bearish"

    def adjust_take_profits(self, current_price, trend):
        """Adjust take profits when more than 6 positions are open"""
        if len(self.active_positions) <= self.adjustment_threshold:
            return

        first_pos = self.active_positions[0]
        last_pos = self.active_positions[-1]
        price_diff = abs(last_pos['price'] - first_pos['price'])
        adjusted_move = price_diff * self.tp_adjustment_percent

        if trend == "bullish":
            new_tp = last_pos['price'] + adjusted_move
        else:
            new_tp = last_pos['price'] - adjusted_move

        # Update all positions' take profits
        for pos in self.active_positions:
            pos['take_profit'] = new_tp

    def should_open_new_position(self, current_price, trend):
        """Check if we should open a new position"""
        if not self.active_positions:
            return True

        last_pos = self.active_positions[-1]
        if trend == "bullish":
            return current_price < last_pos['price'] - self.grid_step
        else:
            return current_price > last_pos['price'] + self.grid_step

    def calculate_position_allocation(self, current_price, trend):
        """Calculate position allocation based on strategy rules"""
        if len(self.active_positions) >= self.max_positions:
            return 0

        # Record new position
        position = {
            'price': current_price,
            'allocation': self.initial_allocation,
            'type': trend,
            'take_profit': current_price + self.tp_distance if trend == "bullish" else current_price - self.tp_distance,
            'stop_loss': current_price - self.sl_distance if trend == "bullish" else current_price + self.sl_distance
        }
        
        self.active_positions.append(position)
        self.adjust_take_profits(current_price, trend)
        
        log(f"Opening new position: {position}")
        return self.initial_allocation

    def run(self, data):
        allocation_dict = {ticker: 0 for ticker in self.tickers}
        ohlcv = data.get("ohlcv")
        
        if not ohlcv or len(ohlcv) < 2:
            return TargetAllocation(allocation_dict)

        current_data = ohlcv[-1]
        current_price = current_data[self.tickers[0]]['close']
        current_date = current_data[self.tickers[0]]['date']

        # Check prices at 5 AM and 9 AM
        if self.is_time_to_check(current_date):
            if current_date not in self.last_check_prices:
                price_5am = ohlcv[-2][self.tickers[0]]['open']
                price_9am = current_price
                
                trend = self.calculate_trend(price_5am, price_9am)
                log(f"Trend detected: {trend} at {current_date}")

                # Check if we should open new position
                if self.should_open_new_position(current_price, trend):
                    allocation = self.calculate_position_allocation(current_price, trend)
                    allocation_dict[self.tickers[0]] = allocation

                self.last_check_prices[current_date] = {
                    'price_5am': price_5am,
                    'price_9am': price_9am
                }

        return TargetAllocation(allocation_dict)
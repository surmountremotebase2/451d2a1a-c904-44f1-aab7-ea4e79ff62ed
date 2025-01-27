from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log

class TradingStrategy(Strategy):
    def __init__(self):
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
        self.last_processed_date = None

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def determine_trend(self, open_price, close_price):
        """Determine trend using open and close prices"""
        trend = "bullish" if close_price > open_price else "bearish"
        log(f"Trend calculation - Open: {open_price}, Close: {close_price}, Trend: {trend}")
        return trend

    def calculate_position_allocation(self, current_price, trend):
        """Calculate position allocation based on strategy rules"""
        if len(self.active_positions) >= self.max_positions:
            log("Maximum positions reached")
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
        log(f"New position opened: {position}")
        
        # Adjust take profits if needed
        if len(self.active_positions) > self.adjustment_threshold:
            self.adjust_take_profits(trend)
            log("Take profits adjusted")
        
        return self.initial_allocation

    def adjust_take_profits(self, trend):
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

        log(f"Adjusting take profits to: {new_tp}")
        for pos in self.active_positions:
            pos['take_profit'] = new_tp

    def should_open_new_position(self, current_price, trend):
        """Check if we should open a new position"""
        if not self.active_positions:
            log("No active positions, opening first position")
            return True

        last_pos = self.active_positions[-1]
        if trend == "bullish":
            should_open = current_price < last_pos['price'] - self.grid_step
            log(f"Bullish check - Last pos price: {last_pos['price']}, Current: {current_price}, Should open: {should_open}")
        else:
            should_open = current_price > last_pos['price'] + self.grid_step
            log(f"Bearish check - Last pos price: {last_pos['price']}, Current: {current_price}, Should open: {should_open}")
        
        return should_open

    def run(self, data):
        allocation_dict = {ticker: 0 for ticker in self.tickers}
        ohlcv = data.get("ohlcv")
        
        if not ohlcv or len(ohlcv) < 2:
            log("Insufficient data")
            return TargetAllocation(allocation_dict)

        current_data = ohlcv[-1]
        ticker_data = current_data[self.tickers[0]]
        current_date = ticker_data['date']
        
        if current_date == self.last_processed_date:
            log(f"Already processed date: {current_date}")
            return TargetAllocation(allocation_dict)

        log(f"\n=== Processing {current_date} ===")
        log(f"Open: {ticker_data['open']}, Close: {ticker_data['close']}")
        
        # Determine trend using open and close prices
        trend = self.determine_trend(ticker_data['open'], ticker_data['close'])
        
        # Check if we should open a new position
        if self.should_open_new_position(ticker_data['close'], trend):
            allocation = self.calculate_position_allocation(ticker_data['close'], trend)
            allocation_dict[self.tickers[0]] = allocation
            log(f"Opening position with allocation: {allocation}")
        
        self.last_processed_date = current_date
        log(f"Final allocation: {allocation_dict}\n")
        
        return TargetAllocation(allocation_dict)
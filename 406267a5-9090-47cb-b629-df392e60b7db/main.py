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
        self.debug_counter = 0

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def is_time_to_check(self, date_str):
        """Check if it's 5 AM or 9 AM"""
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            is_check_time = dt.hour in [5, 9]
            log(f"Time check - Date: {date_str}, Hour: {dt.hour}, Should check: {is_check_time}")
            return is_check_time
        except Exception as e:
            log(f"Error parsing date {date_str}: {str(e)}")
            return False

    def calculate_trend(self, price_5am, price_9am):
        """Determine market trend"""
        trend = "bullish" if price_9am > price_5am else "bearish"
        log(f"Trend calculation - 5AM: {price_5am}, 9AM: {price_9am}, Trend: {trend}")
        return trend

    def should_open_new_position(self, current_price, trend):
        """Check if we should open a new position"""
        if not self.active_positions:
            log("No active positions, should open new position")
            return True

        last_pos = self.active_positions[-1]
        should_open = False
        
        if trend == "bullish":
            price_diff = last_pos['price'] - current_price
            should_open = current_price < last_pos['price'] - self.grid_step
            log(f"Bullish check - Last position price: {last_pos['price']}, Current price: {current_price}")
            log(f"Price difference: {price_diff}, Grid step: {self.grid_step}, Should open: {should_open}")
        else:
            price_diff = current_price - last_pos['price']
            should_open = current_price > last_pos['price'] + self.grid_step
            log(f"Bearish check - Last position price: {last_pos['price']}, Current price: {current_price}")
            log(f"Price difference: {price_diff}, Grid step: {self.grid_step}, Should open: {should_open}")

        return should_open

    def calculate_position_allocation(self, current_price, trend):
        """Calculate position allocation based on strategy rules"""
        log(f"Calculating allocation - Current positions: {len(self.active_positions)}, Max positions: {self.max_positions}")
        
        if len(self.active_positions) >= self.max_positions:
            log("Maximum positions reached, no new allocation")
            return 0

        position = {
            'price': current_price,
            'allocation': self.initial_allocation,
            'type': trend,
            'take_profit': current_price + self.tp_distance if trend == "bullish" else current_price - self.tp_distance,
            'stop_loss': current_price - self.sl_distance if trend == "bullish" else current_price + self.sl_distance
        }
        
        self.active_positions.append(position)
        log(f"New position created: {position}")
        
        if len(self.active_positions) > self.adjustment_threshold:
            self.adjust_take_profits(current_price, trend)
            log("Take profits adjusted due to position threshold")
        
        return self.initial_allocation

    def run(self, data):
        self.debug_counter += 1
        log(f"\n=== Strategy Run #{self.debug_counter} ===")
        
        allocation_dict = {ticker: 0 for ticker in self.tickers}
        ohlcv = data.get("ohlcv")
        
        if not ohlcv:
            log("No OHLCV data available")
            return TargetAllocation(allocation_dict)
        
        if len(ohlcv) < 2:
            log("Insufficient historical data")
            return TargetAllocation(allocation_dict)

        current_data = ohlcv[-1]
        current_price = current_data[self.tickers[0]]['close']
        current_date = current_data[self.tickers[0]]['date']
        
        log(f"Processing - Date: {current_date}, Current Price: {current_price}")
        log(f"Active Positions: {len(self.active_positions)}")

        # Debug OHLCV data structure
        log(f"Current OHLCV data:")
        log(f"Open: {current_data[self.tickers[0]]['open']}")
        log(f"High: {current_data[self.tickers[0]]['high']}")
        log(f"Low: {current_data[self.tickers[0]]['low']}")
        log(f"Close: {current_data[self.tickers[0]]['close']}")
        log(f"Volume: {current_data[self.tickers[0]]['volume']}")

        if self.is_time_to_check(current_date):
            log("Time check passed")
            if current_date not in self.last_check_prices:
                previous_data = ohlcv[-2][self.tickers[0]]
                price_5am = previous_data['open']
                price_9am = current_price
                
                log(f"Price comparison - Previous open (5AM): {price_5am}, Current (9AM): {price_9am}")
                
                trend = self.calculate_trend(price_5am, price_9am)
                
                if self.should_open_new_position(current_price, trend):
                    allocation = self.calculate_position_allocation(current_price, trend)
                    allocation_dict[self.tickers[0]] = allocation
                    log(f"Opening position with allocation: {allocation}")
                else:
                    log("Conditions not met for opening new position")

                self.last_check_prices[current_date] = {
                    'price_5am': price_5am,
                    'price_9am': price_9am
                }
            else:
                log(f"Already processed this date: {current_date}")
        else:
            log("Not a valid check time")

        log(f"Final allocation dictionary: {allocation_dict}")
        log("=== End of Run ===\n")
        return TargetAllocation(allocation_dict)
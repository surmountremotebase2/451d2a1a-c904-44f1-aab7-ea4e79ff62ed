from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from datetime import datetime

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["GLD"]
        self.data_list = []
        
        # Fixed strategy parameters
        self.max_positions = 17
        self.fixed_lot_size = 0.01
        self.fixed_tp_distance = 0.8
        self.fixed_sl_distance = 20.0
        self.grid_spacing = 1.0
        self.adjustment_threshold = 6
        self.tp_adjustment_percent = 0.70
        
        # Position tracking
        self.active_positions = []
        self.total_allocation = 0
        self.last_processed_date = None
        
        # Price tracking for time-based comparison
        self.open_price = None
        self.prev_hour_price = None
        self.day_start = False

    @property
    def interval(self):
        return "1hour"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def determine_trend(self, current_price):
        """Determine trend based on price comparison of 9:30 vs 10:30"""
        if self.open_price is None or self.prev_hour_price is None:
            return None
            
        log(f"Comparing prices - Open(9:30): {self.open_price}, Previous(10:30): {self.prev_hour_price}")
        if self.prev_hour_price > self.open_price:
            return "bullish"
        elif self.prev_hour_price < self.open_price:
            return "bearish"
        return None

    def adjust_take_profits(self):
        """Adjust take profits when there are 6 or more positions"""
        if len(self.active_positions) >= self.adjustment_threshold:
            first_position = self.active_positions[0]['price']
            last_position = self.active_positions[-1]['price']
            price_diff = abs(last_position - first_position)
            adjustment = price_diff * self.tp_adjustment_percent
            
            if self.active_positions[0]['type'] == 'bullish':
                new_tp = last_position + adjustment
            else:
                new_tp = last_position - adjustment
            
            log(f"Adjusting TPs for all positions to {new_tp}")
            for position in self.active_positions:
                position['take_profit'] = new_tp

    def manage_existing_positions(self, current_price, high_price, low_price):
        """Check take profits and stop losses"""
        positions_to_remove = []
        allocation_change = 0
        
        for idx, pos in enumerate(self.active_positions):
            # Check take profits
            if pos['type'] == 'bullish' and high_price >= pos['take_profit']:
                log(f"TP hit for bullish position {idx} at {pos['take_profit']}")
                positions_to_remove.append(pos)
                allocation_change -= self.fixed_lot_size
            elif pos['type'] == 'bearish' and low_price <= pos['take_profit']:
                log(f"TP hit for bearish position {idx} at {pos['take_profit']}")
                positions_to_remove.append(pos)
                allocation_change -= self.fixed_lot_size
                
            # Check stop losses
            elif pos['type'] == 'bullish' and low_price <= pos['stop_loss']:
                log(f"SL hit for bullish position {idx} at {pos['stop_loss']}")
                positions_to_remove.append(pos)
                allocation_change -= self.fixed_lot_size
            elif pos['type'] == 'bearish' and high_price >= pos['stop_loss']:
                log(f"SL hit for bearish position {idx} at {pos['stop_loss']}")
                positions_to_remove.append(pos)
                allocation_change -= self.fixed_lot_size
        
        for pos in positions_to_remove:
            self.active_positions.remove(pos)
        
        return allocation_change

    def should_open_new_position(self, current_price, trend):
        """Check if we should open a new position based on grid spacing"""
        if not self.active_positions:
            return True
            
        last_pos = self.active_positions[-1]
        price_diff = abs(current_price - last_pos['price'])
        log(f"Price diff from last position: {price_diff}")
        
        if trend == "bullish":
            return current_price < last_pos['price'] - self.grid_spacing
        else:
            return current_price > last_pos['price'] + self.grid_spacing

    def run(self, data):
        ohlcv = data.get("ohlcv")
        
        if not ohlcv:
            log("Insufficient data")
            return TargetAllocation({self.tickers[0]: self.total_allocation})

        current_data = ohlcv[-1]
        ticker_data = current_data[self.tickers[0]]
        current_date = datetime.strptime(ticker_data['date'], '%Y-%m-%d %H:%M:%S')
        current_hour = current_date.hour
        current_minute = current_date.minute
        self.current_price = ticker_data['close']

        if current_date == self.last_processed_date:
            return TargetAllocation({self.tickers[0]: self.total_allocation})

        log(f"\n=== Processing {current_date} ===")
        
        # Store 9:30 price
        if current_hour == 9 and current_minute == 30:
            self.open_price = self.current_price
            self.day_start = True
            log(f"Stored 9:30 price: {self.open_price}")
            return TargetAllocation({self.tickers[0]: self.total_allocation})
            
        # Store 10:30 price and determine trend
        if current_hour == 10 and current_minute == 30:
            self.prev_hour_price = self.current_price
            log(f"Stored 10:30 price: {self.prev_hour_price}")
            if self.day_start:
                trend = self.determine_trend(self.current_price)
                if trend and len(self.active_positions) < self.max_positions:
                    # Calculate take profit and stop loss
                    if trend == "bullish":
                        take_profit = self.current_price + self.fixed_tp_distance
                        stop_loss = self.current_price - self.fixed_sl_distance
                    else:
                        take_profit = self.current_price - self.fixed_tp_distance
                        stop_loss = self.current_price + self.fixed_sl_distance
                    
                    # Open first position
                    position = {
                        'price': self.current_price,
                        'allocation': self.fixed_lot_size,
                        'type': trend,
                        'take_profit': take_profit,
                        'stop_loss': stop_loss
                    }
                    
                    self.active_positions.append(position)
                    self.total_allocation += self.fixed_lot_size
                    log(f"First position opened: {position}")
        
        # Reset day start flag at end of day
        if current_hour == 15 and current_minute == 30:
            self.day_start = False
            
        # Manage existing positions and check for new grid positions
        if self.active_positions:
            # Manage existing positions
            allocation_change = self.manage_existing_positions(
                self.current_price,
                ticker_data['high'],
                ticker_data['low']
            )
            self.total_allocation += allocation_change
            
            # Check for new position based on grid
            trend = self.active_positions[0]['type']  # Use trend from first position
            if len(self.active_positions) < self.max_positions:
                if self.should_open_new_position(self.current_price, trend):
                    if trend == "bullish":
                        take_profit = self.current_price + self.fixed_tp_distance
                        stop_loss = self.active_positions[0]['stop_loss']  # Use first position's stop loss
                    else:
                        take_profit = self.current_price - self.fixed_tp_distance
                        stop_loss = self.active_positions[0]['stop_loss']  # Use first position's stop loss
                    
                    position = {
                        'price': self.current_price,
                        'allocation': self.fixed_lot_size,
                        'type': trend,
                        'take_profit': take_profit,
                        'stop_loss': stop_loss
                    }
                    
                    self.active_positions.append(position)
                    self.total_allocation += self.fixed_lot_size
                    log(f"Additional position opened: {position}")
                    
                    # Adjust take profits if necessary
                    self.adjust_take_profits()
        
        self.last_processed_date = current_date
        log(f"Active positions: {len(self.active_positions)}")
        log(f"Final total allocation: {self.total_allocation}\n")
        
        return TargetAllocation({self.tickers[0]: self.total_allocation})
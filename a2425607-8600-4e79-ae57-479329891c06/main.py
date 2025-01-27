from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.technical_indicators import RSI, ATR, SMA

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["GLD"]
        self.data_list = []
        
        # Core technical parameters - optimized for GLD
        self.rsi_period = 12        # Slightly faster RSI
        self.atr_period = 10        # More responsive ATR
        self.vol_period = 15        # More recent volume focus
        self.sma_period = 20        # Trend confirmation
        
        # Strategy parameters
        self.max_positions = 17
        self.max_positions_per_direction = 10  # New: limit positions per direction
        self.base_allocation = 1
        self.max_allocation = 2      # New: cap on position size
        self.adjustment_threshold = 6
        self.tp_adjustment_percent = 0.70
        
        # Dynamic multipliers - optimized
        self.grid_multiplier = 0.4   # Slightly tighter grid
        self.tp_multiplier_normal = 0.9
        self.tp_multiplier_overbought = 0.6
        self.tp_multiplier_oversold = 1.3
        self.sl_multiplier = 2.5     # Slightly tighter stop loss
        self.volume_multiplier = 1.3  # More conservative volume scaling
        
        # Position tracking
        self.active_positions = []
        self.total_allocation = 0
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

    def calculate_average_volume(self, ohlcv, period):
        """Calculate average volume manually"""
        if len(ohlcv) < period:
            return None
        
        volumes = []
        for data in ohlcv[-period:]:
            volumes.append(data[self.tickers[0]]['volume'])
        
        return sum(volumes) / len(volumes)

    def calculate_dynamic_parameters(self, ticker_data, ohlcv):
        """Calculate dynamic strategy parameters based on market conditions"""
        try:
            # Get technical indicators
            rsi = RSI(self.tickers[0], ohlcv, self.rsi_period)
            atr = ATR(self.tickers[0], ohlcv, self.atr_period)
            sma = SMA(self.tickers[0], ohlcv, self.sma_period)
            avg_volume = self.calculate_average_volume(ohlcv, self.vol_period)
            
            if not all([rsi, atr, avg_volume, sma]):
                log("Technical indicators not ready")
                return None
                
            current_rsi = rsi[-1]
            current_atr = atr[-1]
            current_sma = sma[-1]
            
            log(f"Indicators - RSI: {current_rsi}, ATR: {current_atr}, SMA: {current_sma}, Avg Vol: {avg_volume}")
            
            # Dynamic grid spacing based on ATR
            grid_step = current_atr * self.grid_multiplier
            
            # Dynamic take profit based on RSI
            if current_rsi > 70:
                tp_distance = current_atr * self.tp_multiplier_overbought
            elif current_rsi < 30:
                tp_distance = current_atr * self.tp_multiplier_oversold
            else:
                tp_distance = current_atr * self.tp_multiplier_normal
                
            # Dynamic stop loss based on ATR
            sl_distance = current_atr * self.sl_multiplier
            
            # Dynamic position sizing based on volume with cap
            if ticker_data['volume'] > avg_volume * 1.2:
                allocation = min(self.base_allocation * self.volume_multiplier, self.max_allocation)
            else:
                allocation = self.base_allocation
                
            params = {
                'grid_step': grid_step,
                'tp_distance': tp_distance,
                'sl_distance': sl_distance,
                'allocation': allocation,
                'rsi': current_rsi,
                'atr': current_atr,
                'sma': current_sma,
                'avg_volume': avg_volume
            }
            
            log(f"Dynamic Parameters: {params}")
            return params
            
        except Exception as e:
            log(f"Error calculating parameters: {str(e)}")
            return None

    def count_positions_by_type(self, position_type):
        """Count number of positions of a given type"""
        return sum(1 for pos in self.active_positions if pos['type'] == position_type)

    def determine_trend(self, open_price, close_price, rsi, current_sma):
        """Determine trend using price action, RSI, and SMA"""
        price_trend = "bullish" if close_price > open_price else "bearish"
        
        # Consider RSI and SMA for trend confirmation
        if price_trend == "bullish":
            if rsi < 70 and close_price > current_sma:  # Not overbought and above SMA
                trend_strength = "confirmed"
            else:
                trend_strength = "weak"
        else:
            if rsi > 30 and close_price < current_sma:  # Not oversold and below SMA
                trend_strength = "confirmed"
            else:
                trend_strength = "weak"
            
        log(f"Trend calculation - Open: {open_price}, Close: {close_price}, RSI: {rsi}, SMA: {current_sma}")
        log(f"Trend: {price_trend}, Strength: {trend_strength}")
        
        return price_trend if trend_strength == "confirmed" else None

    def manage_existing_positions(self, current_price, high_price, low_price):
        """Check take profits and stop losses"""
        positions_to_remove = []
        allocation_change = 0
        
        for idx, pos in enumerate(self.active_positions):
            # Check take profits
            if pos['type'] == 'bullish' and high_price >= pos['take_profit']:
                log(f"TP hit for bullish position {idx} at {pos['take_profit']}")
                positions_to_remove.append(pos)
                allocation_change -= pos['allocation']
            elif pos['type'] == 'bearish' and low_price <= pos['take_profit']:
                log(f"TP hit for bearish position {idx} at {pos['take_profit']}")
                positions_to_remove.append(pos)
                allocation_change -= pos['allocation']
                
            # Check stop losses
            elif pos['type'] == 'bullish' and low_price <= pos['stop_loss']:
                log(f"SL hit for bullish position {idx} at {pos['stop_loss']}")
                positions_to_remove.append(pos)
                allocation_change -= pos['allocation']
            elif pos['type'] == 'bearish' and high_price >= pos['stop_loss']:
                log(f"SL hit for bearish position {idx} at {pos['stop_loss']}")
                positions_to_remove.append(pos)
                allocation_change -= pos['allocation']
        
        for pos in positions_to_remove:
            self.active_positions.remove(pos)
        
        return allocation_change

    def run(self, data):
        ohlcv = data.get("ohlcv")
        
        if not ohlcv or len(ohlcv) < max(self.rsi_period, self.atr_period, self.vol_period, self.sma_period):
            log("Insufficient data")
            return TargetAllocation({self.tickers[0]: self.total_allocation})

        current_data = ohlcv[-1]
        ticker_data = current_data[self.tickers[0]]
        current_date = ticker_data['date']
        
        if current_date == self.last_processed_date:
            return TargetAllocation({self.tickers[0]: self.total_allocation})

        log(f"\n=== Processing {current_date} ===")
        log(f"Current positions: {len(self.active_positions)}")
        
        # Calculate dynamic parameters
        params = self.calculate_dynamic_parameters(ticker_data, ohlcv)
        if not params:
            return TargetAllocation({self.tickers[0]: self.total_allocation})
        
        # Manage existing positions
        allocation_change = self.manage_existing_positions(
            ticker_data['close'],
            ticker_data['high'],
            ticker_data['low']
        )
        self.total_allocation += allocation_change
        
        # Determine trend
        trend = self.determine_trend(ticker_data['open'], ticker_data['close'], 
                                   params['rsi'], params['sma'])
        
        if trend and len(self.active_positions) < self.max_positions:
            # Check position limits per direction
            current_direction_positions = self.count_positions_by_type(trend)
            if current_direction_positions >= self.max_positions_per_direction:
                log(f"Maximum positions ({self.max_positions_per_direction}) reached for {trend} direction")
                return TargetAllocation({self.tickers[0]: self.total_allocation})
            
            # Check grid spacing
            should_open = True
            if self.active_positions:
                last_pos = self.active_positions[-1]
                if trend == "bullish":
                    should_open = ticker_data['close'] < last_pos['price'] - params['grid_step']
                else:
                    should_open = ticker_data['close'] > last_pos['price'] + params['grid_step']
            
            if should_open:
                position = {
                    'price': ticker_data['close'],
                    'allocation': params['allocation'],
                    'type': trend,
                    'take_profit': ticker_data['close'] + params['tp_distance'] if trend == "bullish" 
                                 else ticker_data['close'] - params['tp_distance'],
                    'stop_loss': ticker_data['close'] - params['sl_distance'] if trend == "bullish"
                                else ticker_data['close'] + params['sl_distance']
                }
                
                self.active_positions.append(position)
                self.total_allocation += params['allocation']
                log(f"New position opened: {position}")
        
        self.last_processed_date = current_date
        log(f"Final total allocation: {self.total_allocation}\n")
        
        return TargetAllocation({self.tickers[0]: self.total_allocation})
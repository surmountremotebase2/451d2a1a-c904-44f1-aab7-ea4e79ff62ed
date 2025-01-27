from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.technical_indicators import RSI, ATR, SMA

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["GLD"]
        self.data_list = []
        
        # Core technical parameters
        self.rsi_period = 12
        self.atr_period = 10
        self.vol_period = 15
        self.sma_period = 20
        self.short_sma_period = 10
        
        # Strategy parameters
        self.max_positions = 17
        self.max_positions_per_direction = 10
        self.base_allocation = 1
        self.max_allocation = 2
        self.adjustment_threshold = 6
        self.tp_adjustment_percent = 0.70
        
        # Risk management parameters
        self.max_daily_positions = 3
        self.daily_positions_opened = 0
        self.last_trading_day = None
        self.max_total_risk = 0.05
        
        # Dynamic multipliers
        self.grid_multiplier = 0.4
        self.tp_multiplier_normal = 0.9
        self.tp_multiplier_overbought = 0.6
        self.tp_multiplier_oversold = 1.3
        self.sl_multiplier = 2.5
        self.volume_multiplier = 1.3
        
        # Position tracking
        self.active_positions = []
        self.total_allocation = 0
        self.last_processed_date = None
        self.total_risk = 0

    @property
    def interval(self):
        """Return the data interval for the strategy"""
        return "1day"

    @property
    def assets(self):
        """Return the list of assets used by the strategy"""
        return self.tickers

    @property
    def data(self):
        """Return the data list used by the strategy"""
        return self.data_list

    def calculate_average_volume(self, ohlcv, period):
        """Calculate average volume manually"""
        if len(ohlcv) < period:
            return None
        
        volumes = []
        for data in ohlcv[-period:]:
            volumes.append(data[self.tickers[0]]['volume'])
        
        return sum(volumes) / len(volumes)

    def calculate_position_risk(self, entry_price, stop_loss, allocation):
        """Calculate risk for a single position"""
        risk_amount = abs(entry_price - stop_loss) * allocation
        return risk_amount / entry_price

    def can_add_position(self, current_date, position_risk):
        """Check if we can add a new position based on risk and daily limits"""
        # Reset daily counter if new day
        current_day = current_date.split(' ')[0]
        if current_day != self.last_trading_day:
            self.daily_positions_opened = 0
            self.last_trading_day = current_day

        # Check daily position limit
        if self.daily_positions_opened >= self.max_daily_positions:
            log(f"Daily position limit ({self.max_daily_positions}) reached")
            return False

        # Check total risk
        if self.total_risk + position_risk > self.max_total_risk:
            log(f"Maximum portfolio risk ({self.max_total_risk*100}%) would be exceeded")
            return False

        return True

    def count_positions_by_type(self, position_type):
        """Count number of positions of a given type"""
        return sum(1 for pos in self.active_positions if pos['type'] == position_type)

    def calculate_dynamic_parameters(self, ticker_data, ohlcv):
        """Calculate dynamic strategy parameters based on market conditions"""
        try:
            # Get technical indicators
            rsi = RSI(self.tickers[0], ohlcv, self.rsi_period)
            atr = ATR(self.tickers[0], ohlcv, self.atr_period)
            sma = SMA(self.tickers[0], ohlcv, self.sma_period)
            short_sma = SMA(self.tickers[0], ohlcv, self.short_sma_period)
            avg_volume = self.calculate_average_volume(ohlcv, self.vol_period)
            
            if not all([rsi, atr, avg_volume, sma, short_sma]):
                log("Technical indicators not ready")
                return None
                
            current_rsi = rsi[-1]
            current_atr = atr[-1]
            current_sma = sma[-1]
            current_short_sma = short_sma[-1]
            
            log(f"Indicators - RSI: {current_rsi}, ATR: {current_atr}, SMA: {current_sma}, Short SMA: {current_short_sma}")
            
            # Market volatility adjustment
            volatility_factor = min(max(current_atr / ticker_data['close'], 0.001), 0.02)
            adjusted_grid = self.grid_multiplier * (1 + volatility_factor)
            
            # Dynamic parameters with volatility adjustment
            grid_step = current_atr * adjusted_grid
            
            # Dynamic take profit based on RSI and volatility
            if current_rsi > 70:
                tp_distance = current_atr * self.tp_multiplier_overbought * (1 - volatility_factor)
            elif current_rsi < 30:
                tp_distance = current_atr * self.tp_multiplier_oversold * (1 + volatility_factor)
            else:
                tp_distance = current_atr * self.tp_multiplier_normal
                
            # Dynamic stop loss based on ATR and volatility
            sl_distance = current_atr * self.sl_multiplier * (1 + volatility_factor)
            
            # Dynamic position sizing based on volume with volatility adjustment
            if ticker_data['volume'] > avg_volume * 1.2:
                allocation = min(self.base_allocation * self.volume_multiplier * (1 - volatility_factor), 
                               self.max_allocation)
            else:
                allocation = self.base_allocation * (1 - volatility_factor)
                
            params = {
                'grid_step': grid_step,
                'tp_distance': tp_distance,
                'sl_distance': sl_distance,
                'allocation': allocation,
                'rsi': current_rsi,
                'atr': current_atr,
                'sma': current_sma,
                'short_sma': current_short_sma,
                'volatility': volatility_factor,
                'avg_volume': avg_volume
            }
            
            log(f"Dynamic Parameters: {params}")
            return params
            
        except Exception as e:
            log(f"Error calculating parameters: {str(e)}")
            return None

    def determine_trend(self, open_price, close_price, params):
        """Enhanced trend determination using multiple indicators"""
        price_trend = "bullish" if close_price > open_price else "bearish"
        
        # Check SMA cross
        sma_cross_bullish = params['short_sma'] > params['sma']
        
        # Enhanced trend confirmation
        if price_trend == "bullish":
            if (params['rsi'] < 70 and 
                close_price > params['sma'] and 
                sma_cross_bullish):
                trend_strength = "confirmed"
            else:
                trend_strength = "weak"
        else:
            if (params['rsi'] > 30 and 
                close_price < params['sma'] and 
                not sma_cross_bullish):
                trend_strength = "confirmed"
            else:
                trend_strength = "weak"
            
        log(f"Trend calculation - Open: {open_price}, Close: {close_price}, "
            f"RSI: {params['rsi']}, SMA Cross Bullish: {sma_cross_bullish}")
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
        """Main strategy execution method"""
        ohlcv = data.get("ohlcv")
        required_periods = max(self.rsi_period, self.atr_period, self.vol_period, 
                             self.sma_period, self.short_sma_period)
        
        if not ohlcv or len(ohlcv) < required_periods:
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
        
        # Update total risk for closed positions
        self.total_risk = sum(self.calculate_position_risk(pos['price'], pos['stop_loss'], pos['allocation'])
                            for pos in self.active_positions)
        
        # Determine trend
        trend = self.determine_trend(ticker_data['open'], ticker_data['close'], params)
        
        if trend and len(self.active_positions) < self.max_positions:
            # Calculate potential position risk
            potential_stop = (ticker_data['close'] - params['sl_distance'] if trend == "bullish"
                            else ticker_data['close'] + params['sl_distance'])
            position_risk = self.calculate_position_risk(ticker_data['close'], potential_stop, params['allocation'])
            
            # Check if we can add position
            if not self.can_add_position(current_date, position_risk):
                return TargetAllocation({self.tickers[0]: self.total_allocation})
            
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
                    'take_profit': (ticker_data['close'] + params['tp_distance'] if trend == "bullish"
                                  else ticker_data['close'] - params['tp_distance']),
                    'stop_loss': potential_stop
                }
                
                self.active_positions.append(position)
                self.total_allocation += params['allocation']
                self.total_risk += position_risk
                self.daily_positions_opened += 1
                log(f"New position opened: {position}")
        
        self.last_processed_date = current_date
        log(f"Active positions: {len(self.active_positions)}")
        log(f"Daily positions opened: {self.daily_positions_opened}")
        log(f"Total risk: {self.total_risk*100:.2f}%")
        log(f"Total allocation: {self.total_allocation}\n")
        
        return TargetAllocation({self.tickers[0]: self.total_allocation})
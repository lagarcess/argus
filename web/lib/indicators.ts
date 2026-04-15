export interface IndicatorMetadata {
  id: string;
  name: string;
  category: 'Trend' | 'Momentum' | 'Volatility' | 'Volume' | 'Other';
  description: string;
  defaultPeriod: number;
}

export const INDICATOR_REGISTRY: IndicatorMetadata[] = [
  // Trend
  { id: 'SMA', name: 'Simple Moving Average', category: 'Trend', description: 'Average price over a specific number of periods.', defaultPeriod: 10 },
  { id: 'EMA', name: 'Exponential Moving Average', category: 'Trend', description: 'Weighted average that gives more importance to recent price data.', defaultPeriod: 10 },
  { id: 'WMA', name: 'Weighted Moving Average', category: 'Trend', description: 'Weighted average where more recent data is more significant.', defaultPeriod: 10 },
  { id: 'HMA', name: 'Hull Moving Average', category: 'Trend', description: 'Smoothed moving average with reduced lag.', defaultPeriod: 10 },
  { id: 'VWAP', name: 'Volume Weighted Average Price', category: 'Trend', description: 'Average price based on both volume and price.', defaultPeriod: 1 },

  // Momentum
  { id: 'RSI', name: 'Relative Strength Index', category: 'Momentum', description: 'Measures the speed and change of price movements.', defaultPeriod: 14 },
  { id: 'MACD', name: 'MACD', category: 'Momentum', description: 'Trend-following momentum indicator that shows the relationship between two moving averages.', defaultPeriod: 12 },
  { id: 'STOCH', name: 'Stochastic Oscillator', category: 'Momentum', description: 'Compares a specific closing price of an asset to a range of its prices over a certain period.', defaultPeriod: 14 },
  { id: 'CMO', name: 'Chande Momentum Oscillator', category: 'Momentum', description: 'Modified RSI that measures momentum directly.', defaultPeriod: 14 },
  { id: 'WILLR', name: 'Williams %R', category: 'Momentum', description: 'Momentum indicator that measures overbought and oversold levels.', defaultPeriod: 14 },
  { id: 'CCI', name: 'Commodity Channel Index', category: 'Momentum', description: 'Measures the current price level relative to an average price level.', defaultPeriod: 20 },

  // Volatility
  { id: 'ATR', name: 'Average True Range', category: 'Volatility', description: 'Measures market volatility by decomposing the entire range of an asset price for that period.', defaultPeriod: 14 },
  { id: 'BBANDS', name: 'Bollinger Bands', category: 'Volatility', description: 'Volatility bands placed above and below a moving average.', defaultPeriod: 20 },
  { id: 'KC', name: 'Keltner Channels', category: 'Volatility', description: 'Volatility-based envelopes set above and below an exponential moving average.', defaultPeriod: 20 },

  // Volume
  { id: 'OBV', name: 'On-Balance Volume', category: 'Volume', description: 'Uses volume flow to predict changes in stock price.', defaultPeriod: 1 },
  { id: 'CMF', name: 'Chaikin Money Flow', category: 'Volume', description: 'Measures the amount of Money Flow Volume over a specific period.', defaultPeriod: 20 },
  { id: 'AD', name: 'Accumulation/Distribution', category: 'Volume', description: 'Uses volume to confirm price trends or warn of weak movements.', defaultPeriod: 1 },

  // Custom/Other
  { id: 'MFI', name: 'Money Flow Index', category: 'Momentum', description: 'Uses price and volume for identifying overbought or oversold signals.', defaultPeriod: 14 },
];

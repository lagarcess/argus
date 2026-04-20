export interface AssetRegistryItem {
  symbol: string;
  name: string;
  category: 'EQUITY' | 'CRYPTO' | 'ETF';
  exchange: string;
}

export const ASSET_REGISTRY: AssetRegistryItem[] = [
  // Equities
  { symbol: 'AAPL', name: 'Apple Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'MSFT', name: 'Microsoft Corp.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'NVDA', name: 'NVIDIA Corp.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'AMZN', name: 'Amazon.com Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'META', name: 'Meta Platforms Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'TSLA', name: 'Tesla Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'AMD', name: 'Advanced Micro Devices', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'NFLX', name: 'Netflix Inc.', category: 'EQUITY', exchange: 'NASDAQ' },
  { symbol: 'BRK.B', name: 'Berkshire Hathaway', category: 'EQUITY', exchange: 'NYSE' },

  // ETFs
  { symbol: 'SPY', name: 'SPDR S&P 500 ETF', category: 'ETF', exchange: 'NYSE' },
  { symbol: 'QQQ', name: 'Invesco QQQ Trust', category: 'ETF', exchange: 'NASDAQ' },
  { symbol: 'IWM', name: 'iShares Russell 2000', category: 'ETF', exchange: 'NYSE' },

  // Crypto
  { symbol: 'BTC/USD', name: 'Bitcoin', category: 'CRYPTO', exchange: 'CBSE' },
  { symbol: 'ETH/USD', name: 'Ethereum', category: 'CRYPTO', exchange: 'CBSE' },
  { symbol: 'SOL/USD', name: 'Solana', category: 'CRYPTO', exchange: 'CBSE' },
  { symbol: 'BTC/USDT', name: 'Bitcoin (Tether)', category: 'CRYPTO', exchange: 'BINANCE' },
  { symbol: 'ETH/USDT', name: 'Ethereum (Tether)', category: 'CRYPTO', exchange: 'BINANCE' },
];

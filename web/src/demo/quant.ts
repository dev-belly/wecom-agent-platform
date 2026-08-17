// 由 src/factors 引擎真实计算生成（scripts/compute_demo.py），非手抄。
import type { QuantData } from '../types'

export const QUANT_DATA: QuantData = {
  market_name: "沪深300(合成基准)",
  per_stock: {
    "688001.SH": {
      code: "688001.SH", name: "\u661f\u8fb0\u79d1\u6280", price: 149.46,
      risk: {
        annual_return: 0.4983, annual_vol: 0.2991, sharpe: 1.502,
        sortino: 1.541, max_drawdown: -0.3141, calmar: 1.587,
        beta: 1.117, alpha: 0.3542, var_95_annual: -0.4565,
        cvar_95_annual: -0.6043, skew: -0.094, kurtosis: 0.053
      },
      style: {
        momentum_20: 0.0007, momentum_60: 0.1442, momentum_120: 0.4593,
        volatility_annual: 0.2991, recent_20d_return: 0.0007
      }
    },
    "600519.SH": {
      code: "600519.SH", name: "\u9ed4\u98ce\u767d\u9152", price: 5780.27,
      risk: {
        annual_return: 0.4844, annual_vol: 0.2086, sharpe: 1.999,
        sortino: 2.066, max_drawdown: -0.1072, calmar: 4.518,
        beta: 0.731, alpha: 0.39, var_95_annual: -0.3277,
        cvar_95_annual: -0.4035, skew: -0.088, kurtosis: -0.165
      },
      style: {
        momentum_20: 0.1583, momentum_60: 0.2755, momentum_120: 0.3329,
        volatility_annual: 0.2086, recent_20d_return: 0.1583
      }
    },
    "300750.SZ": {
      code: "300750.SZ", name: "\u8fdc\u521b\u65b0\u80fd", price: 310.67,
      risk: {
        annual_return: 0.1718, annual_vol: 0.3559, sharpe: 0.623,
        sortino: 0.638, max_drawdown: -0.408, calmar: 0.421,
        beta: 0.903, alpha: 0.0553, var_95_annual: -0.5614,
        cvar_95_annual: -0.7073, skew: -0.044, kurtosis: -0.269
      },
      style: {
        momentum_20: -0.0152, momentum_60: -0.2154, momentum_120: -0.2465,
        volatility_annual: 0.3559, recent_20d_return: -0.0152
      }
    },
    "601318.SH": {
      code: "601318.SH", name: "601318.SH", price: 51.07,
      risk: {
        annual_return: 0.0218, annual_vol: 0.1873, sharpe: 0.208,
        sortino: 0.21, max_drawdown: -0.266, calmar: 0.082,
        beta: 0.504, alpha: -0.0432, var_95_annual: -0.3054,
        cvar_95_annual: -0.3737, skew: 0.039, kurtosis: -0.109
      },
      style: {
        momentum_20: -0.0546, momentum_60: -0.1772, momentum_120: -0.0126,
        volatility_annual: 0.1873, recent_20d_return: -0.0546
      }
    },
    "000858.SZ": {
      code: "000858.SZ", name: "000858.SZ", price: 382.73,
      risk: {
        annual_return: 0.3546, annual_vol: 0.2626, sharpe: 1.288,
        sortino: 1.322, max_drawdown: -0.2133, calmar: 1.662,
        beta: 0.979, alpha: 0.2283, var_95_annual: -0.4082,
        cvar_95_annual: -0.5046, skew: 0.039, kurtosis: -0.156
      },
      style: {
        momentum_20: 0.1234, momentum_60: 0.2365, momentum_120: 0.0796,
        volatility_annual: 0.2626, recent_20d_return: 0.1234
      }
    },
  },
  leaderboard: [
    {
      code: "600519.SH", name: "\u9ed4\u98ce\u767d\u9152", momentum: 0.2755,
      low_vol: -0.2086, beta: 0.731, sharpe: 1.999,
      quality: 0.2799, growth: 0.202, value: 0.1756,
      z_momentum: 1.071, z_low_vol: 0.886, z_quality: 1.165,
      z_growth: 0.46, z_value: 1.181, composite_score: 0.953, rank: 1
    },
    {
      code: "688001.SH", name: "\u661f\u8fb0\u79d1\u6280", momentum: 0.1442,
      low_vol: -0.2991, beta: 1.117, sharpe: 1.502,
      quality: 0.2959, growth: 0.2916, value: 0.1833,
      z_momentum: 0.44, z_low_vol: -0.596, z_quality: 1.274,
      z_growth: 1.192, z_value: 1.267, composite_score: 0.715, rank: 2
    },
    {
      code: "000858.SZ", name: "000858.SZ", momentum: 0.2365,
      low_vol: -0.2626, beta: 0.979, sharpe: 1.288,
      quality: 0.0, growth: 0.0, value: 0.0,
      z_momentum: 0.883, z_low_vol: 0.002, z_quality: -0.737,
      z_growth: -1.191, z_value: -0.79, composite_score: -0.366, rank: 3
    },
    {
      code: "601318.SH", name: "601318.SH", momentum: -0.1772,
      low_vol: -0.1873, beta: 0.504, sharpe: 0.208,
      quality: 0.0, growth: 0.0, value: 0.0,
      z_momentum: -1.105, z_low_vol: 1.235, z_quality: -0.737,
      z_growth: -1.191, z_value: -0.79, composite_score: -0.517, rank: 4
    },
    {
      code: "300750.SZ", name: "\u8fdc\u521b\u65b0\u80fd", momentum: -0.2154,
      low_vol: -0.3559, beta: 0.903, sharpe: 0.623,
      quality: -0.0337, growth: 0.2351, value: -0.007,
      z_momentum: -1.288, z_low_vol: -1.527, z_quality: -0.966,
      z_growth: 0.73, z_value: -0.868, composite_score: -0.784, rank: 5
    },
  ],
  reports: {
    "688001.SH": {
      code: "688001.SH", name: "\u661f\u8fb0\u79d1\u6280", found: true,
      years: [2022, 2023, 2024, 2025],
      ratios: [
        {
          year: 2022, gross_margin: 0.4322, net_margin: 0.2098,
          roe: 0.2229, roa: 0.1285, debt_to_assets: 0.4228,
          current_ratio: 1.421, quick_ratio: 1.212,
          ar_turnover_days: 71.3, ocf_to_net_profit: 1.133,
          revenue_yoy: null, net_profit_yoy: null
        },
        {
          year: 2023, gross_margin: 0.3954, net_margin: 0.1534,
          roe: 0.165, roa: 0.0969, debt_to_assets: 0.4129,
          current_ratio: 1.503, quick_ratio: 1.247,
          ar_turnover_days: 64.8, ocf_to_net_profit: 1.041,
          revenue_yoy: 0.3294, net_profit_yoy: -0.0281
        },
        {
          year: 2024, gross_margin: 0.4299, net_margin: 0.2082,
          roe: 0.2746, roa: 0.1496, debt_to_assets: 0.4552,
          current_ratio: 1.507, quick_ratio: 1.261,
          ar_turnover_days: 68.4, ocf_to_net_profit: 1.133,
          revenue_yoy: 0.3061, net_profit_yoy: 0.7727
        },
        {
          year: 2025, gross_margin: 0.4132, net_margin: 0.1713,
          roe: 0.2959, roa: 0.1417, debt_to_assets: 0.5213,
          current_ratio: 1.259, quick_ratio: 0.983,
          ar_turnover_days: 60.5, ocf_to_net_profit: 1.118,
          revenue_yoy: 0.2916, net_profit_yoy: 0.0629
        },
      ],
      latest: {
        year: 2025, gross_margin: 0.4132, net_margin: 0.1713,
        roe: 0.2959, roa: 0.1417, debt_to_assets: 0.5213,
        current_ratio: 1.259, quick_ratio: 0.983,
        ar_turnover_days: 60.5, ocf_to_net_profit: 1.118,
        revenue_yoy: 0.2916, net_profit_yoy: 0.0629
      },
      anomalies: [
      ],
      anomaly_count: 0
    },
    "600519.SH": {
      code: "600519.SH", name: "\u9ed4\u98ce\u767d\u9152", found: true,
      years: [2022, 2023, 2024, 2025],
      ratios: [
        {
          year: 2022, gross_margin: 0.5275, net_margin: 0.2721,
          roe: 0.1939, roa: 0.1198, debt_to_assets: 0.3824,
          current_ratio: 1.641, quick_ratio: 1.445,
          ar_turnover_days: 61.8, ocf_to_net_profit: 1.103,
          revenue_yoy: null, net_profit_yoy: null
        },
        {
          year: 2023, gross_margin: 0.5349, net_margin: 0.2953,
          roe: 0.252, roa: 0.1456, debt_to_assets: 0.4224,
          current_ratio: 1.576, quick_ratio: 1.37,
          ar_turnover_days: 62.9, ocf_to_net_profit: 1.098,
          revenue_yoy: 0.2275, net_profit_yoy: 0.3321
        },
        {
          year: 2024, gross_margin: 0.512, net_margin: 0.2643,
          roe: 0.2351, roa: 0.1228, debt_to_assets: 0.4774,
          current_ratio: 1.376, quick_ratio: 1.16,
          ar_turnover_days: 75.9, ocf_to_net_profit: 1.034,
          revenue_yoy: 0.1884, net_profit_yoy: 0.0637
        },
        {
          year: 2025, gross_margin: 0.5135, net_margin: 0.2687,
          roe: 0.2799, roa: 0.1403, debt_to_assets: 0.4987,
          current_ratio: 1.388, quick_ratio: 1.211,
          ar_turnover_days: 66.2, ocf_to_net_profit: 1.106,
          revenue_yoy: 0.202, net_profit_yoy: 0.2219
        },
      ],
      latest: {
        year: 2025, gross_margin: 0.5135, net_margin: 0.2687,
        roe: 0.2799, roa: 0.1403, debt_to_assets: 0.4987,
        current_ratio: 1.388, quick_ratio: 1.211,
        ar_turnover_days: 66.2, ocf_to_net_profit: 1.106,
        revenue_yoy: 0.202, net_profit_yoy: 0.2219
      },
      anomalies: [
      ],
      anomaly_count: 0
    },
    "300750.SZ": {
      code: "300750.SZ", name: "\u8fdc\u521b\u65b0\u80fd", found: true,
      years: [2022, 2023, 2024, 2025],
      ratios: [
        {
          year: 2022, gross_margin: 0.1629, net_margin: -0.0429,
          roe: -0.0371, roa: -0.0229, debt_to_assets: 0.3811,
          current_ratio: 1.745, quick_ratio: 1.485,
          ar_turnover_days: 66.1, ocf_to_net_profit: 1.069,
          revenue_yoy: null, net_profit_yoy: null
        },
        {
          year: 2023, gross_margin: 0.1703, net_margin: -0.0286,
          roe: -0.0275, roa: -0.0159, debt_to_assets: 0.4224,
          current_ratio: 1.483, quick_ratio: 1.263,
          ar_turnover_days: 72.1, ocf_to_net_profit: 1.069,
          revenue_yoy: 0.2276, net_profit_yoy: -0.1813
        },
        {
          year: 2024, gross_margin: 0.1713, net_margin: -0.013,
          roe: -0.0151, roa: -0.0083, debt_to_assets: 0.45,
          current_ratio: 1.487, quick_ratio: 1.246,
          ar_turnover_days: 72.3, ocf_to_net_profit: 1.114,
          revenue_yoy: 0.3271, net_profit_yoy: -0.3969
        },
        {
          year: 2025, gross_margin: 0.1699, net_margin: -0.0257,
          roe: -0.0337, roa: -0.0175, debt_to_assets: 0.4793,
          current_ratio: 1.483, quick_ratio: 1.232,
          ar_turnover_days: 70.1, ocf_to_net_profit: 1.14,
          revenue_yoy: 0.2351, net_profit_yoy: 1.443
        },
      ],
      latest: {
        year: 2025, gross_margin: 0.1699, net_margin: -0.0257,
        roe: -0.0337, roa: -0.0175, debt_to_assets: 0.4793,
        current_ratio: 1.483, quick_ratio: 1.232,
        ar_turnover_days: 70.1, ocf_to_net_profit: 1.14,
        revenue_yoy: 0.2351, net_profit_yoy: 1.443
      },
      anomalies: [
        { level: "mid", rule: "\u6bdb\u5229\u7387 < 20%", value: 0.1699 },
      ],
      anomaly_count: 1
    },
  },
  backtest: {
    meta: {
      strategy_name: "\u52a8\u91cf\u56e0\u5b50(ROC20/60) 688001.SH", symbol: "688001.SH",
      start: "2023-06-19", end: "2025-12-31",
      initial_cash: 1000000.0, market: "china_a"
    },
    summary: {
      total_return_pct: 128.63017839027955, annual_return_pct: 36.9964930975585,
      max_drawdown_pct: 8.858550576870428, sharpe: 2.36728312833478,
      win_rate_pct: 75.0, total_trades: 16
    }
  }
}

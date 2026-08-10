"use client";

import * as React from "react";

import type { PriceHistoryPoint } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";

interface CandlestickChartProps {
  data: PriceHistoryPoint[];
  currency?: string;
}

const WIDTH = 1000;
const HEIGHT = 320;
const PRICE_TOP = 14;
const PRICE_BOTTOM = 226;
const VOL_TOP = 246;
const VOL_BOTTOM = 306;

type OhlcPoint = PriceHistoryPoint & { open: number; high: number; low: number };

function hasOhlc(point: PriceHistoryPoint): point is OhlcPoint {
  return point.open != null && point.high != null && point.low != null;
}

/** Real daily OHLCV candles from Yahoo Finance (app/market_data on the
 * backend) — never synthesized. Falls back to null when a series has no
 * usable OHLC (e.g. intraday-only ranges some tickers don't populate). */
export function CandlestickChart({ data, currency = "INR" }: CandlestickChartProps) {
  const candles = React.useMemo(() => data.filter(hasOhlc), [data]);

  if (candles.length < 2) return null;

  const priceMin = Math.min(...candles.map((c) => c.low));
  const priceMax = Math.max(...candles.map((c) => c.high));
  const pricePad = (priceMax - priceMin) * 0.08 || priceMax * 0.02 || 1;
  const domainMin = priceMin - pricePad;
  const domainMax = priceMax + pricePad;
  const volMax = Math.max(...candles.map((c) => c.volume ?? 0), 1);

  const step = WIDTH / candles.length;
  const bodyWidth = Math.max(step * 0.55, 1.5);

  const y = (price: number) =>
    PRICE_BOTTOM - ((price - domainMin) / (domainMax - domainMin)) * (PRICE_BOTTOM - PRICE_TOP);

  const gridLevels = [0, 1, 2, 3].map((i) => domainMin + ((domainMax - domainMin) * i) / 3);
  const tickIndexes = [0, Math.floor(candles.length / 2), candles.length - 1];

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-full w-full" preserveAspectRatio="none">
      {gridLevels.map((level) => (
        <g key={level}>
          <line
            x1={0}
            x2={WIDTH}
            y1={y(level)}
            y2={y(level)}
            stroke="#ffffff0d"
            strokeWidth={1}
          />
          <text x={WIDTH - 6} y={y(level) - 4} textAnchor="end" fontSize={11} fill="var(--neutral-700)">
            {formatCurrency(level, currency)}
          </text>
        </g>
      ))}

      {candles.map((candle, i) => {
        const up = candle.close >= candle.open;
        const color = up ? "var(--gain)" : "var(--loss)";
        const cx = i * step + step / 2;
        const bodyTop = y(Math.max(candle.open, candle.close));
        const bodyBottom = y(Math.min(candle.open, candle.close));
        const barHeight = Math.max(bodyBottom - bodyTop, 1);
        const vol = candle.volume ?? 0;
        const volHeight = (vol / volMax) * (VOL_BOTTOM - VOL_TOP);

        return (
          <g key={candle.date}>
            <line
              x1={cx}
              x2={cx}
              y1={y(candle.high)}
              y2={y(candle.low)}
              stroke={color}
              strokeWidth={1.2}
            />
            <rect
              x={cx - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={barHeight}
              fill={color}
              fillOpacity={0.35}
              stroke={color}
              strokeWidth={1}
            />
            <rect
              x={cx - bodyWidth / 2}
              y={VOL_BOTTOM - volHeight}
              width={bodyWidth}
              height={volHeight}
              fill={color}
              fillOpacity={0.22}
            />
          </g>
        );
      })}

      {tickIndexes.map((i, tickPosition) => (
        <text
          key={i}
          x={i * step + step / 2}
          y={HEIGHT - 2}
          textAnchor={tickPosition === 0 ? "start" : tickPosition === tickIndexes.length - 1 ? "end" : "middle"}
          fontSize={11}
          fill="var(--neutral-700)"
        >
          {formatDate(candles[i].date)}
        </text>
      ))}
    </svg>
  );
}

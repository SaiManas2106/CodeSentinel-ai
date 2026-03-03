"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import type { TrendData } from "@/lib/types";

interface TrendChartProps {
  data: TrendData[];
}

export default function TrendChart({ data }: TrendChartProps): JSX.Element {
  return (
    <div className="h-80 w-full rounded-lg border border-border bg-card p-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" />
          <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" />
          <Tooltip formatter={(value: number) => `${value.toFixed(1)}`} />
          <Legend verticalAlign="bottom" />
          <Line type="monotone" dataKey="overall" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="security" stroke="#ef4444" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="standards" stroke="#10b981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

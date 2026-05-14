"use client"

import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts"

interface HistoryEntry {
  round:      number | null
  track_name: string | null
  position:   number | null
  points:     number
}

interface Props { history: HistoryEntry[] }

export function ResultsChart({ history }: Props) {
  const data = history.map((h) => ({
    name: h.track_name ? h.track_name.split(" ")[0] : `R${h.round}`,
    pos:  h.position ?? null,
    pts:  h.points,
  }))

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
        <XAxis
          dataKey="name"
          tick={{ fill: "#6b6b80", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          reversed
          domain={[1, 20]}
          ticks={[1, 5, 10, 15, 20]}
          tick={{ fill: "#6b6b80", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{ background: "#1a1a22", border: "1px solid #2a2a36", borderRadius: 8 }}
          labelStyle={{ color: "#e8e8f0" }}
          formatter={(v: number) => [`P${v}`, "Позиция"]}
        />
        <ReferenceLine y={3}  stroke="#2a2a36" strokeDasharray="3 3" />
        <ReferenceLine y={10} stroke="#2a2a36" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="pos"
          stroke="#e10600"
          strokeWidth={2}
          dot={{ fill: "#e10600", r: 3 }}
          activeDot={{ r: 5 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--color-bg)",
        surface: "var(--color-surface-1)",
        surfaceAlt: "var(--color-surface-2)",
        panel: "var(--color-surface-3)",
        border: "var(--color-border)",
        borderStrong: "var(--color-border-strong)",
        text: "var(--color-text-primary)",
        muted: "var(--color-text-secondary)",
        dim: "var(--color-text-muted)",
        accent: "var(--color-accent)",
        amber: "var(--color-amber)",
        success: "var(--color-success)",
        info: "var(--color-info)",
        danger: "var(--color-danger)",
      },
      fontFamily: {
        sans: ["var(--font-body)", "ui-sans-serif", "sans-serif"],
        display: ["var(--font-display)", "ui-sans-serif", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        float: "0 18px 48px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
}

export default config

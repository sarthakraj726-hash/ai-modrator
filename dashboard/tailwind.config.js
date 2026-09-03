/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#08090f",
        surface: "#0f111d",
        "surface-raised": "#16192b",
        "surface-border": "#21253d",
        cyber: {
          purple: "#9333ea",
          neon: "#a855f7",
          cyan: "#06b6d4",
          electric: "#22d3ee",
          emerald: "#10b981",
          amber: "#f59e0b",
          rose: "#f43f5e",
        },
      },
      fontFamily: {
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
        sans: ["var(--font-sans)", "Inter", "sans-serif"],
      },
      boxShadow: {
        "glow-purple": "0 0 25px -5px rgba(168, 85, 247, 0.3)",
        "glow-cyan": "0 0 25px -5px rgba(6, 182, 212, 0.3)",
        "glow-rose": "0 0 25px -5px rgba(244, 63, 94, 0.3)",
      },
    },
  },
  plugins: [],
};

import typography from "@tailwindcss/typography";
import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: { DEFAULT: token("surface"), 2: token("surface-2") },
        muted: token("muted"),
        line: { DEFAULT: token("border"), strong: token("border-strong") },
        fg: { DEFAULT: token("fg"), muted: token("fg-muted"), subtle: token("fg-subtle") },
        accent: { DEFAULT: token("accent"), fg: token("accent-fg") },
        sidebar: {
          DEFAULT: token("sidebar"),
          fg: token("sidebar-fg"),
          muted: token("sidebar-muted"),
          line: token("sidebar-border"),
          hover: token("sidebar-hover"),
        },
        success: token("success"),
        warning: token("warning"),
        danger: token("danger"),
        info: token("info"),
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
        flash: { "0%, 100%": { backgroundColor: "transparent" }, "30%": { backgroundColor: "rgb(var(--warning) / 0.18)" } },
        slide: { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(300%)" } },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out both",
        flash: "flash 1.6s ease-in-out",
      },
    },
  },
  plugins: [typography],
};

export default config;

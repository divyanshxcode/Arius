/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070b10",
        panel: "#0d141c",
        line: "#1b2836",
        muted: "#7d90a4",
        mint: "#3ddc97",
        cyan: "#4cc9f0",
        amber: "#f4b860",
        rose: "#ff6b6b",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#1f2229",
        panelHeader: "#262a33",
        appbg: "#181a1f",
        border: "#33363f",
        accent: "#3b82f6",
        online: "#22c55e",
        offline: "#ef4444",
      },
    },
  },
  plugins: [],
};

import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: { colors: { trikaaya: { dark: "#101B2D", lemon: "#C7F464", cream: "#F7F9FC", olive: "#2563EB", navy: "#101B2D", slate: "#64748B" } }, fontFamily: { sans: ["Manrope", "Arial", "sans-serif"] } } },
  plugins: []
};
export default config;

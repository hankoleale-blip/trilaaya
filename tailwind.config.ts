import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: { colors: { trikaaya: { dark: "#20251F", lemon: "#E8EF63", cream: "#F4F5E9", olive: "#A8B33B" } }, fontFamily: { sans: ["Manrope", "Arial", "sans-serif"] } } },
  plugins: []
};
export default config;

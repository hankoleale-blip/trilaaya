import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "Trikaaya Sports | Train with purpose", description: "Taekwondo training built around movement, focus, discipline and confidence." };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }

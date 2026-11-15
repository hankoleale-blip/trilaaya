import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "Trikaaya Sports | TRI · FORM · BODY", description: "Build strength, discipline and confidence with Trikaaya Sports." };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }

import { Fraunces, Manrope } from "next/font/google";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const ui = Manrope({ subsets: ["latin"], variable: "--font-ui", display: "swap" });

export const metadata = {
  title: "Director",
  description: "A node canvas for any brand: describe what you want, wire the steps, run them with a cost you can see.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${ui.variable}`}>
      <body>{children}</body>
    </html>
  );
}

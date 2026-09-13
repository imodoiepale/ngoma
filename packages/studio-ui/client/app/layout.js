import { Fraunces, Manrope } from "next/font/google";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const ui = Manrope({ subsets: ["latin"], variable: "--font-ui", display: "swap" });

export const metadata = {
  title: "EPALLE Studio",
  description: "Client workflows on a node canvas: ideas become pipelines you can edit, combine and check.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${ui.variable}`}>
      <body>{children}</body>
    </html>
  );
}

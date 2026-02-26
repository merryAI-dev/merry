import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Space_Grotesk, Noto_Sans_KR } from "next/font/google";
import "./globals.css";

const fontSans = Space_Grotesk({
  variable: "--font-merry-sans",
  subsets: ["latin"],
  display: "swap",
});

const fontDisplay = Fraunces({
  variable: "--font-merry-display",
  subsets: ["latin"],
  display: "swap",
});

const fontMono = IBM_Plex_Mono({
  variable: "--font-merry-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

const fontKorean = Noto_Sans_KR({
  variable: "--font-korean",
  subsets: ["latin"],
  weight: ["400", "700", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Merry",
    template: "%s · Merry",
  },
  description: "VC collaboration workspace for analysis, drafts, and reviews.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="light" style={{ colorScheme: "light" }}>
      <body
        className={`${fontSans.variable} ${fontDisplay.variable} ${fontMono.variable} ${fontKorean.variable} antialiased`}
        style={{ background: "#ffffff", color: "#001e46" }}
      >
        {children}
      </body>
    </html>
  );
}

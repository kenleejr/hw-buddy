import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Homework Buddy",
  description: "AI-powered homework assistance with real-time audio",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body suppressHydrationWarning={true}>
        {children}
      </body>
    </html>
  );
}
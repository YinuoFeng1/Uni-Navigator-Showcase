import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Uni-Navigator",
  description:
    "A source-aware university policy assistant prototype for HCI research.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-[var(--background-main)] text-[var(--text-primary)] antialiased">
        {children}
      </body>
    </html>
  );
}

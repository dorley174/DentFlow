import type { Metadata } from "next";
import "./globals.css";
import "./refinements.css";
import { ToastProvider } from "@/components/ui";

export const metadata: Metadata = {
  title: {
    default: "DentFlow — больше заботы, меньше рутины",
    template: "%s · DentFlow",
  },
  description:
    "AI-администратор, онлайн-запись и CRM в единой платформе для российских стоматологий.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}

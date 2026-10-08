import { notFound } from "next/navigation";
import BusinessApp from "@/components/business-app/BusinessApp";

export const metadata = { title: "Business preview (sample data) - Cuadrao" };
export const dynamic = "force-dynamic";

export default function BusinessPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <main className="min-h-[100dvh] bg-background text-foreground">
      <BusinessApp sampleData />
    </main>
  );
}

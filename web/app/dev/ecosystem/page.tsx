import { notFound } from "next/navigation";
import EcosystemPreview from "./EcosystemPreview";

export const metadata = { title: "Ecosystem preview · Argus" };
export const dynamic = "force-dynamic";

export default function EcosystemPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <EcosystemPreview />;
}

import AuthLanding from "@/components/auth/AuthLanding";
import GuestEntry from "@/components/guest/GuestEntry";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function LandingPage() {
  const guestAccessEnabled =
    process.env.NEXT_PUBLIC_GUEST_ACCESS_ENABLED === "true";

  return guestAccessEnabled ? <GuestEntry /> : <AuthLanding />;
}

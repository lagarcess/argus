import { handleSignup } from "@/lib/forms/signup";
import { signupDeps } from "@/lib/forms/runtime";

export function POST(request: Request) {
  return handleSignup(request, signupDeps());
}

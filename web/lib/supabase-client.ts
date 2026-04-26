import { createClient } from "@supabase/supabase-js";

// Use a mock url during build if NEXT_PUBLIC_SUPABASE_URL is not set
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:54321";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSJ9.xxxxx";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

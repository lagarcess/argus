import { createClient } from '@supabase/supabase-js'

// Using the provided environment variable names directly.
// These are shimmed in next.config.ts for browser accessibility.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    'Supabase environment variables are missing. ' +
    'Ensure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set in your web/.env.local file and restart the server.'
  )
}

export const supabase = createClient(supabaseUrl!, supabaseAnonKey!)

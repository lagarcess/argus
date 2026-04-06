import { createClient } from '@supabase/supabase-js'

// Using the provided environment variable names directly.
// These are shimmed in next.config.ts for browser accessibility.
const supabaseUrl = process.env.SUPABASE_URL
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    'Supabase environment variables are missing. ' +
    'Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in your web/.env file and restart the server.'
  )
}

export const supabase = createClient(supabaseUrl!, supabaseAnonKey!)

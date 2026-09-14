// Release builds pin NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL. The fallback is the API's
// SUPPORT_EMAIL_ADDRESS; tests/test_support_email_agreement.py fails if they differ.
const configured = process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "";

export const supportEmail = configured.trim() || "support@get-argus.com";

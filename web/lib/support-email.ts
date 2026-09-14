import supportContact from "../argus_display_contract/support_contact.json";

// Release builds pin NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL; unset or blank uses the address
// the API reads from the same contract file.
const configured = process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "";

export const supportEmail = configured.trim() || supportContact.email;

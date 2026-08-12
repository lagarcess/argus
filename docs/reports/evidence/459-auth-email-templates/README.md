# Supabase Auth email template snapshot

This directory is a one-time restore and diff snapshot of the 13 Supabase Auth email templates configured for Argus on 2026-08-12. Supabase remains the live owner. These files are not a sync mechanism and no deployment tooling reads them.

All bodies contain English and es-419 branches selected from the user's stored language. Supabase stores the HTML body; the Supabase-to-Resend SMTP path emits the delivered multipart alternative with generated plain text. The live action-link expiry was 60 minutes at capture time. The shared header uses the canonical PNG at `https://arguschat.ai/icons/argus-192.png` with a visible `ARGUS` text fallback, table-based email layout, and Space Grotesk or Inter stacks that fall back to Arial and Helvetica without loading remote fonts.

A fresh hosted recovery message on 2026-08-12 passed SPF, DKIM, and DMARC in Gmail's raw headers. Its plain-text and HTML parts both used a recovery `redirect_to` host of `arguschat.ai`; the link was not opened.

| Supabase template | Subject template | Snapshot |
| --- | --- | --- |
| Confirm signup | `{{ if eq .Data.language "es-419" }}Argus: confirma tu correo{{ else }}Argus: confirm your email{{ end }}` | [confirmation.html](./confirmation.html) |
| Invite user | `{{ if eq .Data.language "es-419" }}Argus: tu invitación{{ else }}Argus: your invitation{{ end }}` | [invite.html](./invite.html) |
| Magic link or OTP | `{{ if eq .Data.language "es-419" }}Argus: tu enlace de acceso{{ else }}Argus: your sign-in link{{ end }}` | [magic-link.html](./magic-link.html) |
| Change email address | `{{ if eq .Data.language "es-419" }}Argus: confirma tu nuevo correo{{ else }}Argus: confirm your new email{{ end }}` | [email-change.html](./email-change.html) |
| Reset password | `{{ if eq .Data.language "es-419" }}Argus: restablece tu contraseña{{ else }}Argus: reset your password{{ end }}` | [recovery.html](./recovery.html) |
| Reauthentication | `{{ if eq .Data.language "es-419" }}Argus: {{ .Token }} es tu código de verificación{{ else }}Argus: {{ .Token }} is your verification code{{ end }}` | [reauthentication.html](./reauthentication.html) |
| Password changed | `{{ if eq .Data.language "es-419" }}Argus: tu contraseña cambió{{ else }}Argus: your password changed{{ end }}` | [password-changed-notification.html](./password-changed-notification.html) |
| Email address changed | `{{ if eq .Data.language "es-419" }}Argus: tu correo cambió{{ else }}Argus: your email changed{{ end }}` | [email-changed-notification.html](./email-changed-notification.html) |
| Phone number changed | `{{ if eq .Data.language "es-419" }}Argus: tu teléfono cambió{{ else }}Argus: your phone number changed{{ end }}` | [phone-changed-notification.html](./phone-changed-notification.html) |
| Sign-in method linked | `{{ if eq .Data.language "es-419" }}Argus: se vinculó un método de acceso{{ else }}Argus: a sign-in method was linked{{ end }}` | [identity-linked-notification.html](./identity-linked-notification.html) |
| Sign-in method removed | `{{ if eq .Data.language "es-419" }}Argus: se eliminó un método de acceso{{ else }}Argus: a sign-in method was removed{{ end }}` | [identity-unlinked-notification.html](./identity-unlinked-notification.html) |
| Verification method added | `{{ if eq .Data.language "es-419" }}Argus: se agregó un método de verificación{{ else }}Argus: a verification method was added{{ end }}` | [mfa-factor-enrolled-notification.html](./mfa-factor-enrolled-notification.html) |
| Verification method removed | `{{ if eq .Data.language "es-419" }}Argus: se eliminó un método de verificación{{ else }}Argus: a verification method was removed{{ end }}` | [mfa-factor-unenrolled-notification.html](./mfa-factor-unenrolled-notification.html) |

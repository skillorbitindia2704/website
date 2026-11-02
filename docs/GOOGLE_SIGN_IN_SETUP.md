# Google Sign-In Setup

The login page displays **Continue with Google** only after both OAuth credentials are configured.

## 1. Create Google OAuth credentials

1. Open Google Cloud Console: https://console.cloud.google.com/
2. Create/select a project and configure the OAuth consent screen.
3. Create an OAuth Client ID with application type **Web application**.
4. Add the website origin under **Authorized JavaScript origins**:
   - `https://www.skillorbitindia.in`
5. Add this exact URL under **Authorized redirect URIs**:
   - `https://www.skillorbitindia.in/login/google/callback`
6. Copy the Client ID and Client Secret.

If the production site uses a different canonical hostname, use that exact hostname consistently in the origin, redirect URI, and `GOOGLE_REDIRECT_URI`.

## 2. Add environment variables in Render

In the Skill Orbit India web service, open **Environment** and add:

- `GOOGLE_CLIENT_ID` = OAuth Client ID from Google Cloud
- `GOOGLE_CLIENT_SECRET` = OAuth Client Secret from Google Cloud
- `GOOGLE_REDIRECT_URI` = `https://www.skillorbitindia.in/login/google/callback`

Do not commit these secrets to GitHub. Restart/redeploy the Render service after saving them.

For local development, use the matching local callback URI in both Google Cloud Console and `GOOGLE_REDIRECT_URI`, for example `http://localhost:5000/login/google/callback`.

## 3. Account behavior

- New Google sign-ins create a **Student** account.
- If a verified Google email already exists in Skill Orbit India, the Google identity is linked to that existing account; its existing role and permissions are preserved.
- Disabled accounts and unapproved teacher accounts cannot sign in.
- A Google identity can be linked to only one local account.
- Existing email/password login continues to work.
- Google identities are stored in the new `google_identity` table; existing user password hashes are not replaced.

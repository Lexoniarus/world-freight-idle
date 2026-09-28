import { createClient } from "@supabase/supabase-js";

/** Own the browser's Supabase session and automatic token refresh. */
export class SupabaseBrowserAuth {
  /** @param {{url: string, publishable_key: string}} config
   * @param {typeof createClient} [clientFactory] */
  constructor(config, clientFactory = createClient) {
    this.client = clientFactory(config.url, config.publishable_key, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }

  /** Return the current raw session token for forwarding to FastAPI.
   * @returns {Promise<string>}
   */
  async accessToken() {
    const { data, error } = await this.client.auth.getSession();
    if (error) throw new Error("Die Anmeldung konnte nicht geprüft werden.");
    return data.session?.access_token ?? "";
  }

  /** Register through Supabase Auth without exposing privileged keys.
   * @returns {Promise<boolean>} Whether a signed-in session is ready.
   */
  async register(email, password, username) {
    const { data, error } = await this.client.auth.signUp({
      email,
      password,
      options: { data: { username } },
    });
    if (error) throw new Error("Das Konto konnte nicht erstellt werden.");
    return Boolean(data.session);
  }

  /** Authenticate an existing Supabase user. @returns {Promise<void>} */
  async login(email, password) {
    const { error } = await this.client.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw new Error("E-Mail oder Passwort ist falsch.");
  }

  /** Revoke the browser session at Supabase. @returns {Promise<void>} */
  async logout() {
    const { error } = await this.client.auth.signOut();
    if (error) throw new Error("Die Abmeldung ist fehlgeschlagen.");
  }

  /** Release the SDK's refresh timer. @returns {void} */
  destroy() {
    this.client.auth.stopAutoRefresh();
  }
}

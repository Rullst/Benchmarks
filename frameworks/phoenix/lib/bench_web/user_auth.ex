defmodule BenchWeb.UserAuth do
  @moduledoc """
  The plugs and helpers of the UserAuth module `mix phx.gen.auth` (Phoenix
  1.8) generates, for a password login: no remember-me cookie, magic links or
  sudo mode, which the benchmark does not use.
  """
  use BenchWeb, :verified_routes

  import Plug.Conn
  import Phoenix.Controller

  alias Bench.Accounts
  alias Bench.Accounts.Scope

  @doc "Logs the user in: a new session holding a fresh session token."
  def log_in_user(conn, user) do
    user_return_to = get_session(conn, :user_return_to)
    token = Accounts.generate_user_session_token(user)

    conn
    |> renew_session()
    |> put_session(:user_token, token)
    |> redirect(to: user_return_to || ~p"/me")
  end

  # Renews the session ID and erases the whole session (fixation attacks).
  defp renew_session(conn) do
    delete_csrf_token()

    conn
    |> configure_session(renew: true)
    |> clear_session()
  end

  @doc "Authenticates the user by the session token in the session (one query)."
  def fetch_current_scope_for_user(conn, _opts) do
    with token when is_binary(token) <- get_session(conn, :user_token),
         {user, _token_inserted_at} <- Accounts.get_user_by_session_token(token) do
      assign(conn, :current_scope, Scope.for_user(user))
    else
      _ -> assign(conn, :current_scope, Scope.for_user(nil))
    end
  end

  @doc "Requires a signed-in user; otherwise redirects to the login page."
  def require_authenticated_user(conn, _opts) do
    if conn.assigns.current_scope && conn.assigns.current_scope.user do
      conn
    else
      conn
      |> put_flash(:error, "You must log in to access this page.")
      |> maybe_store_return_to()
      |> redirect(to: ~p"/login")
      |> halt()
    end
  end

  defp maybe_store_return_to(%{method: "GET"} = conn) do
    put_session(conn, :user_return_to, current_path(conn))
  end

  defp maybe_store_return_to(conn), do: conn
end

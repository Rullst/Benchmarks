defmodule BenchWeb.UserController do
  use BenchWeb, :controller

  # GET /me: fetch_current_scope_for_user loaded the user (one query joining
  # users_tokens and users, on every request) and require_authenticated_user
  # redirected the request to /login if there was none.
  def me(conn, _params) do
    user = conn.assigns.current_scope.user
    json(conn, %{id: user.id, username: user.username, displayName: user.display_name})
  end
end

defmodule BenchWeb.UserSessionController do
  @moduledoc """
  The generated UserSessionController's password login, with a username
  (generated: email) posted as top-level `username` and `password` fields.
  """
  use BenchWeb, :controller

  alias Bench.Accounts
  alias BenchWeb.UserAuth

  plug :put_root_layout, false

  def new(conn, _params) do
    render(conn, :new)
  end

  def create(conn, %{"username" => username, "password" => password}) do
    if user = Accounts.get_user_by_username_and_password(username, password) do
      UserAuth.log_in_user(conn, user)
    else
      conn
      |> put_flash(:error, "Invalid username or password")
      |> redirect(to: ~p"/login")
    end
  end
end

defmodule Bench.Accounts do
  @moduledoc """
  The parts of the Accounts context `mix phx.gen.auth` (Phoenix 1.8) generates
  that a password login and a session need, on the shared `users` table
  (bench/db/phase2.sql): users sign in with a username instead of an email.
  """

  alias Bench.Repo
  alias Bench.Accounts.{User, UserToken}

  def get_user_by_username_and_password(username, password)
      when is_binary(username) and is_binary(password) do
    user = Repo.get_by(User, username: username)
    if User.valid_password?(user, password), do: user
  end

  @doc "Generates a session token and stores it in users_tokens."
  def generate_user_session_token(user) do
    {token, user_token} = UserToken.build_session_token(user)
    Repo.insert!(user_token)
    token
  end

  @doc "The user of a valid session token and the token's creation time (one query joining users_tokens and users)."
  def get_user_by_session_token(token) do
    {:ok, query} = UserToken.verify_session_token_query(token)
    Repo.one(query)
  end
end

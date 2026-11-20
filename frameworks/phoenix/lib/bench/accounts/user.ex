defmodule Bench.Accounts.User do
  @moduledoc """
  The generated User schema on the shared `users` table: `username` and
  `display_name` instead of the generated email and confirmation columns, and
  the bcrypt hash read from `password_bcrypt` (the generated column is
  `hashed_password`).
  """
  use Ecto.Schema

  schema "users" do
    field :username, :string
    field :display_name, :string
    field :hashed_password, :string, source: :password_bcrypt, redact: true
    field :authenticated_at, :utc_datetime, virtual: true
  end

  @doc "Verifies the password with Bcrypt (bcrypt_elixir), as generated."
  def valid_password?(%__MODULE__{hashed_password: hashed_password}, password)
      when is_binary(hashed_password) and byte_size(password) > 0 do
    Bcrypt.verify_pass(password, hashed_password)
  end

  def valid_password?(_, _) do
    Bcrypt.no_user_verify()
    false
  end
end

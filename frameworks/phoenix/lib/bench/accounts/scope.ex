defmodule Bench.Accounts.Scope do
  @moduledoc "The generated Scope: the caller's user, or nil."
  alias Bench.Accounts.User

  defstruct user: nil

  def for_user(%User{} = user), do: %__MODULE__{user: user}
  def for_user(nil), do: nil
end

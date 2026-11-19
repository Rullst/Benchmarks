defmodule Bench.Fortune do
  @moduledoc "The benchmark's existing `fortune` table."
  use Ecto.Schema

  schema "fortune" do
    field :message, :string
  end
end

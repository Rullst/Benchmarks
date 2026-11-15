defmodule Bench.World do
  @moduledoc "The benchmark's existing `world` table."
  use Ecto.Schema

  schema "world" do
    field :randomnumber, :integer
  end
end

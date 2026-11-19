defmodule BenchWeb.BenchController do
  use BenchWeb, :controller

  alias Bench.{Repo, World}

  def plaintext(conn, _params) do
    text(conn, "Hello World")
  end

  def message(conn, _params) do
    json(conn, %{message: "Hello World"})
  end

  def db_single(conn, _params) do
    world = Repo.get!(World, 1)
    json(conn, %{id: world.id, randomNumber: world.randomnumber})
  end

  # One Ecto query per row.
  def queries(conn, params) do
    worlds =
      for _ <- 1..query_count(params["queries"]) do
        world = Repo.get!(World, random_id())
        %{id: world.id, randomNumber: world.randomnumber}
      end

    json(conn, worlds)
  end

  # Each row read with its own query, given a new random value and updated
  # through a changeset, in one transaction; the ids are sorted so that
  # concurrent requests lock rows in the same order.
  def updates(conn, params) do
    ids = Enum.sort(for _ <- 1..query_count(params["queries"]), do: random_id())

    {:ok, worlds} =
      Repo.transaction(fn ->
        Enum.map(ids, fn id ->
          world = Repo.get!(World, id)
          value = new_random_number(world.randomnumber)
          world |> Ecto.Changeset.change(randomnumber: value) |> Repo.update!()
          %{id: id, randomNumber: value}
        end)
      end)

    json(conn, worlds)
  end

  # TechEmpower's rule: an integer clamped to 1..500, anything else is 1.
  defp query_count(value) when is_binary(value) do
    case Integer.parse(value) do
      {count, ""} -> count |> max(1) |> min(500)
      _ -> 1
    end
  end

  defp query_count(_value), do: 1

  defp random_id, do: :rand.uniform(10_000)

  # A new value, different from the current one (so that the row changes).
  defp new_random_number(current) do
    case random_id() do
      ^current -> new_random_number(current)
      value -> value
    end
  end
end

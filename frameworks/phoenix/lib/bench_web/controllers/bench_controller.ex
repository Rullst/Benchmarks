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
  # through a changeset (one UPDATE per row, no transaction). Every Repo call
  # checks a connection out of the pool and returns it, as for /queries, so
  # no request holds a connection while its 20 reads and writes run (a
  # transaction did, and under 125 connections the pool's queue dropped
  # requests: see README.md).
  def updates(conn, params) do
    worlds =
      for _ <- 1..query_count(params["queries"]) do
        world = Repo.get!(World, random_id())
        value = new_random_number(world.randomnumber)
        world |> Ecto.Changeset.change(randomnumber: value) |> Repo.update!()
        %{id: world.id, randomNumber: value}
      end

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

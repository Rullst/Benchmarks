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
end

defmodule BenchWeb.FortuneController do
  use BenchWeb, :controller

  alias Bench.{Fortune, Repo}

  def index(conn, _params) do
    fortunes =
      [%Fortune{id: 0, message: "Additional fortune added at request time."} | Repo.all(Fortune)]
      |> Enum.sort_by(& &1.message)

    render(conn, :index, fortunes: fortunes)
  end
end

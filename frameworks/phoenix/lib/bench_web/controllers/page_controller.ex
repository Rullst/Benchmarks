defmodule BenchWeb.PageController do
  use BenchWeb, :controller

  # Renders page_html/hello.html.heex inside the root layout.
  def hello(conn, _params) do
    render(conn, :hello, name: "World")
  end
end

defmodule BenchWeb.Router do
  use BenchWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {BenchWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  # The HTML page goes through the generated browser pipeline.
  scope "/", BenchWeb do
    pipe_through :browser

    get "/html", PageController, :hello
  end

  # The other endpoints go through the generated API pipeline.
  scope "/", BenchWeb do
    pipe_through :api

    get "/text", BenchController, :plaintext
    get "/json", BenchController, :message
    get "/db-single", BenchController, :db_single
  end
end

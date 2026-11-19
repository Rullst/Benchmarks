defmodule BenchWeb.Router do
  use BenchWeb, :router

  # As `mix phx.gen.auth` adds it.
  import BenchWeb.UserAuth

  pipeline :browser do
    # Benchmark: "json" too, so that GET /me (Accept: application/json)
    # answers JSON (generated: ["html"]).
    plug :accepts, ["html", "json"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {BenchWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  # Benchmark: /fortunes renders HTML without a session or CSRF token.
  pipeline :plain_html do
    plug :accepts, ["html"]
  end

  # The HTML page and the form go through the generated browser pipeline.
  scope "/", BenchWeb do
    pipe_through :browser

    get "/html", PageController, :hello
    get "/form", FormController, :new
    post "/form", FormController, :create
  end

  # The login and /me: the browser pipeline plus the user lookup that
  # phx.gen.auth adds to it (here only on these routes, so /html and /form
  # keep the generated pipeline).
  scope "/", BenchWeb do
    pipe_through [:browser, :fetch_current_scope_for_user]

    get "/login", UserSessionController, :new
    post "/login", UserSessionController, :create
  end

  scope "/", BenchWeb do
    pipe_through [:browser, :fetch_current_scope_for_user, :require_authenticated_user]

    get "/me", UserController, :me
  end

  # The other endpoints go through the generated API pipeline. PUT /world/:id
  # is a public JSON API call: the API pipeline has no CSRF protection.
  scope "/", BenchWeb do
    pipe_through :api

    get "/text", BenchController, :plaintext
    get "/json", BenchController, :message
    get "/db-single", BenchController, :db_single
    get "/queries", BenchController, :queries
    get "/updates", BenchController, :updates
    get "/world/:id", WorldController, :show
    put "/world/:id", WorldController, :update
    get "/worlds", WorldController, :index
  end

  scope "/", BenchWeb do
    pipe_through :plain_html

    get "/fortunes", FortuneController, :index
  end
end

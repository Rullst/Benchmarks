# As `mix phx.new bench --no-assets --no-dashboard --no-gettext --no-mailer
# --no-live` generates it (Phoenix 1.8.16, PostgreSQL, Bandit), without the
# dev/test-only dependencies (phoenix_live_reload, lazy_html). The framework,
# LiveView (HEEx), Ecto, the PostgreSQL driver and Bandit are pinned exactly;
# mix.lock pins the rest.
defmodule Bench.MixProject do
  use Mix.Project

  def project do
    [
      app: :bench,
      version: "0.1.0",
      elixir: "~> 1.17",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps(),
      compilers: [:phoenix_live_view] ++ Mix.compilers(),
      listeners: [Phoenix.CodeReloader]
    ]
  end

  # Configuration for the OTP application.
  #
  # Type `mix help compile.app` for more information.
  def application do
    [
      mod: {Bench.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  # Specifies which paths to compile per environment.
  defp elixirc_paths(_), do: ["lib"]

  # Specifies your project dependencies.
  #
  # Type `mix help deps` for examples and options.
  defp deps do
    [
      {:phoenix, "1.8.16"},
      {:phoenix_ecto, "~> 4.5"},
      {:ecto_sql, "3.14.0"},
      {:postgrex, "0.22.4"},
      {:phoenix_html, "~> 4.1"},
      {:phoenix_live_view, "1.2.13"},
      {:telemetry_metrics, "~> 1.0"},
      {:telemetry_poller, "~> 1.0"},
      {:jason, "~> 1.2"},
      {:dns_cluster, "~> 0.2.0"},
      {:bandit, "1.14.1"},
      # Benchmark: added as `mix phx.gen.auth` adds it (the login checks
      # users.password_bcrypt with it).
      {:bcrypt_elixir, "3.3.2"}
    ]
  end

  # Aliases are shortcuts or tasks specific to the current project.
  #
  # See the documentation for `Mix` for more info on aliases.
  defp aliases do
    [
      setup: ["deps.get"]
    ]
  end
end

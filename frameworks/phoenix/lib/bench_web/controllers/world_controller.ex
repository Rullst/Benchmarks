defmodule BenchWeb.WorldController do
  @moduledoc """
  GET /world/:id, GET /worlds and PUT /world/:id (docs/v2-phase2-spec.md,
  section 3). A non-integer id makes `Repo.get` raise Ecto.Query.CastError,
  which phoenix_ecto answers 400. The query string and the body are
  validated with schemaless changesets (422).
  """
  use BenchWeb, :controller

  import Ecto.Changeset
  import Ecto.Query, only: [from: 2]

  alias Bench.{Repo, World}

  def show(conn, %{"id" => id}) do
    case Repo.get(World, id) do
      nil -> not_found(conn)
      world -> json(conn, %{id: world.id, randomNumber: world.randomnumber})
    end
  end

  @worlds_types %{min: :integer, max: :integer, limit: :integer, page: :integer}
  @worlds_defaults %{min: 1, max: 10_000, limit: 20, page: 1}

  # One query: the filter, ORDER BY, LIMIT and OFFSET run in PostgreSQL.
  def index(conn, params) do
    changeset =
      {@worlds_defaults, @worlds_types}
      |> cast(params, Map.keys(@worlds_types))
      |> validate_required(Map.keys(@worlds_types))
      |> validate_number(:min, greater_than_or_equal_to: 1, less_than_or_equal_to: 10_000)
      |> validate_number(:max, greater_than_or_equal_to: 1, less_than_or_equal_to: 10_000)
      |> validate_number(:limit, greater_than_or_equal_to: 1, less_than_or_equal_to: 100)
      |> validate_number(:page, greater_than_or_equal_to: 1, less_than_or_equal_to: 1000)
      |> validate_min_not_above_max()

    case apply_action(changeset, :validate) do
      {:ok, q} ->
        worlds =
          Repo.all(
            from w in World,
              where: w.id >= ^q.min and w.id <= ^q.max,
              order_by: w.id,
              limit: ^q.limit,
              offset: ^((q.page - 1) * q.limit),
              select: %{id: w.id, randomNumber: w.randomnumber}
          )

        json(conn, worlds)

      {:error, changeset} ->
        unprocessable(conn, changeset)
    end
  end

  # The body is validated before the row is loaded, so a refused request
  # writes nothing; then the usual get, change and Repo.update!.
  def update(conn, %{"id" => id} = params) do
    changeset =
      {%{}, %{randomNumber: :integer}}
      |> cast(params, [:randomNumber])
      |> validate_required([:randomNumber])
      |> validate_number(:randomNumber, greater_than_or_equal_to: 1, less_than_or_equal_to: 10_000)
      |> validate_json_integer(params["randomNumber"])

    with {:ok, %{randomNumber: value}} <- apply_action(changeset, :update),
         %World{} = world <- Repo.get(World, id) do
      world = world |> change(randomnumber: value) |> Repo.update!()
      json(conn, %{id: world.id, randomNumber: world.randomnumber})
    else
      nil -> not_found(conn)
      {:error, changeset} -> unprocessable(conn, changeset)
    end
  end

  defp validate_min_not_above_max(changeset) do
    if changeset.valid? and get_field(changeset, :min) > get_field(changeset, :max) do
      add_error(changeset, :min, "must not be greater than max")
    else
      changeset
    end
  end

  # cast/3 turns the JSON string "5" into 5; the body's value must be a JSON integer.
  defp validate_json_integer(changeset, value) when is_integer(value), do: changeset
  defp validate_json_integer(changeset, _value), do: add_error(changeset, :randomNumber, "must be a JSON integer")

  defp not_found(conn) do
    conn |> put_status(:not_found) |> json(%{errors: %{detail: "Not Found"}})
  end

  defp unprocessable(conn, changeset) do
    errors = Enum.map(changeset.errors, fn {field, {message, _opts}} -> %{field: field, message: message} end)
    conn |> put_status(422) |> json(%{errors: errors})
  end
end

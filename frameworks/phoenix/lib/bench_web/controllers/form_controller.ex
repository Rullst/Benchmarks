defmodule BenchWeb.FormController do
  @moduledoc """
  GET /form and POST /form (docs/v3-spec.md, section 4), in the
  browser pipeline: protect_from_forgery checks the token (403 when forged),
  then a schemaless changeset validates the fields (422).
  """
  use BenchWeb, :controller

  import Ecto.Changeset

  # The pages are whole documents (no root layout).
  plug :put_root_layout, false

  @types %{name: :string, randomNumber: :integer}

  def new(conn, _params) do
    render(conn, :new)
  end

  def create(conn, params) do
    changeset =
      {%{}, @types}
      |> cast(params, Map.keys(@types))
      |> validate_required(Map.keys(@types))
      |> validate_length(:name, min: 1, max: 64, count: :codepoints)
      |> validate_number(:randomNumber, greater_than_or_equal_to: 1, less_than_or_equal_to: 10_000)

    case apply_action(changeset, :insert) do
      {:ok, form} -> render(conn, :create, name: form.name, random_number: form.randomNumber)
      {:error, _changeset} -> conn |> put_status(422) |> render(:new)
    end
  end
end

defmodule BenchWeb.Layouts do
  @moduledoc """
  This module holds layouts and related functionality
  used by your application.

  Benchmark: only the root layout, which is the document the benchmark
  specifies (without the generated app layout, assets and CSRF meta tag).
  """
  use BenchWeb, :html

  embed_templates "layouts/*"
end

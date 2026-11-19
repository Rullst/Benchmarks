defmodule BenchWeb.FortuneHTML do
  use BenchWeb, :html

  def index(assigns) do
    ~H"""
    <!DOCTYPE html><html><head><title>Fortunes</title></head><body><table><tr><th>id</th><th>message</th></tr><tr :for={fortune <- @fortunes}><td>{fortune.id}</td><td>{fortune.message}</td></tr></table></body></html>
    """
  end
end

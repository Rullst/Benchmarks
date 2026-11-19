defmodule BenchWeb.FormHTML do
  use BenchWeb, :html

  def new(assigns) do
    ~H"""
    <!DOCTYPE html><html><head><title>Form</title></head><body><form method="post" action="/form"><input type="hidden" name="_csrf_token" value={get_csrf_token()} /><input type="text" name="name" /><input type="number" name="randomNumber" /><button type="submit">Send</button></form></body></html>
    """
  end

  def create(assigns) do
    ~H"""
    <!DOCTYPE html><html><head><title>Form</title></head><body><h1>Hello, {@name}</h1><p>{@random_number}</p></body></html>
    """
  end
end

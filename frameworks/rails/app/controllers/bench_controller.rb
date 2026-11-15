class BenchController < ApplicationController
  def hello_text
    render plain: "Hello World"
  end

  def hello_json
    render json: { message: "Hello World" }
  end

  def db_single
    world = World.find(1)
    render json: { id: world.id, randomNumber: world.randomnumber }
  end

  # Renders app/views/bench/hello_html.html.erb (the app has no layout).
  def hello_html
    @name = "World"
  end
end

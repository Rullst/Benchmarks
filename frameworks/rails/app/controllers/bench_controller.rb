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

  # One query per row. Active Record's query cache, which Rails enables for
  # every request, is turned off here: a repeated id must be read again.
  def queries
    worlds = World.uncached do
      Array.new(query_count) { World.find(random_id) }
    end
    render json: worlds.map { |world| { id: world.id, randomNumber: world.randomnumber } }
  end

  # Each row read with its own query, given a new random value and saved, in
  # one transaction; the ids are sorted so that concurrent requests lock rows
  # in the same order.
  def updates
    worlds = World.uncached do
      World.transaction do
        Array.new(query_count) { random_id }.sort.map do |id|
          world = World.find(id)
          world.randomnumber = new_random_number(world.randomnumber)
          world.save!
          { id: world.id, randomNumber: world.randomnumber }
        end
      end
    end
    render json: worlds
  end

  # Renders app/views/bench/fortunes.html.erb, without a layout.
  def fortunes
    @fortunes = Fortune.all.to_a
    @fortunes << Fortune.new(id: 0, message: "Additional fortune added at request time.")
    @fortunes.sort_by!(&:message)
    render layout: false
  end

  private
    # TechEmpower's rule: an integer clamped to 1..500, anything else is 1.
    def query_count
      Integer(params[:queries].to_s, 10, exception: false).to_i.clamp(1, 500)
    end

    def random_id
      rand(1..10_000)
    end

    # A new value, different from the current one (so that the row changes).
    def new_random_number(current)
      value = random_id
      value = random_id while value == current
      value
    end
end

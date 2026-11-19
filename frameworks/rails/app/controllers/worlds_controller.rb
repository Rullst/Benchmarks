# GET /world/:id, GET /worlds and PUT /world/:id (docs/v3-spec.md,
# section 3). The route constraint answers 404 for a non-integer id.
class WorldsController < ApplicationController
  # PUT /world/:id is a public JSON API call, sent without cookies: the
  # documented exemption from the CSRF check ActionController::Base applies.
  skip_forgery_protection only: :update

  def show
    world = World.find_by(id: params[:id])
    return head :not_found unless world

    render json: { id: world.id, randomNumber: world.randomnumber }
  end

  # One query: the filter, ORDER BY, LIMIT and OFFSET run in PostgreSQL.
  def index
    query = WorldsQuery.new(params.permit(:min, :max, :limit, :page))
    return render json: { errors: query.errors }, status: 422 if query.invalid?

    worlds = World.where(id: query.min_id..query.max_id).order(:id)
      .limit(query.page_size).offset(query.offset)
    render json: worlds.map { |world| { id: world.id, randomNumber: world.randomnumber } }
  end

  # The body is validated before the row is loaded, so a refused request
  # writes nothing; then the usual load, assign and save (update!, in the
  # transaction Active Record opens for a save).
  def update
    change = WorldUpdate.new(randomNumber: params[:randomNumber])
    return render json: { errors: change.errors }, status: 422 if change.invalid?

    world = World.find_by(id: params[:id])
    return head :not_found unless world

    world.update!(randomnumber: change.randomNumber)
    render json: { id: world.id, randomNumber: world.randomnumber }
  end
end

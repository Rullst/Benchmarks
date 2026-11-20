# GET /form and POST /form (docs/v3-spec.md, section 4). The CSRF check
# is ActionController::Base's default protect_from_forgery (the token in the
# encrypted cookie session, the masked authenticity_token field); a forged
# post raises InvalidAuthenticityToken, answered 422.
class FormsController < ApplicationController
  layout false

  def new
    @form = GreetingForm.new
  end

  def create
    @form = GreetingForm.new(params.permit(:name, :randomNumber))
    if @form.valid?
      render :create
    else
      render :new, status: 422
    end
  end
end

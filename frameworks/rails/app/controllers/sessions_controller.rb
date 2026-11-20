# The SessionsController `bin/rails generate authentication` writes, with the
# changes marked "Benchmark:".
class SessionsController < ApplicationController
  # Benchmark: the generator includes Authentication in ApplicationController;
  # here only the controllers of /login and /me include it, so the other
  # endpoints keep their stack (docs/v3-spec.md, section 2.3).
  include Authentication
  allow_unauthenticated_access only: %i[ new create ]
  # Benchmark: without the generated
  #   rate_limit to: 10, within: 3.minutes, only: :create
  # which would refuse the harness's 125 logins from 127.0.0.1 in every round.
  layout false

  def new
  end

  # Benchmark: username instead of the generated email_address.
  def create
    if user = User.authenticate_by(params.permit(:username, :password))
      start_new_session_for user
      redirect_to after_authentication_url
    else
      redirect_to new_session_path, alert: "Try another username or password."
    end
  end

  def destroy
    terminate_session
    redirect_to new_session_path, status: :see_other
  end
end

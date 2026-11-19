# GET /me: Authentication's before_action resumes the session (the sessions
# row named by the signed session_id cookie) or redirects to /login; the
# user's row is then loaded through the session's association.
class UsersController < ApplicationController
  include Authentication

  def me
    user = Current.user
    render json: { id: user.id, username: user.username, displayName: user.display_name }
  end
end

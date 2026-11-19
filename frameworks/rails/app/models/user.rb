# The User model `bin/rails generate authentication` writes, on the shared
# users table (bench/db/phase2.sql), which keeps the bcrypt hash in
# password_bcrypt instead of the generated password_digest column.
class User < ApplicationRecord
  alias_attribute :password_digest, :password_bcrypt
  has_secure_password
  has_many :sessions, dependent: :destroy
end

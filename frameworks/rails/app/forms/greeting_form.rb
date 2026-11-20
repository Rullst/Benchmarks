# The fields of POST /form.
class GreetingForm
  include ActiveModel::API

  attr_accessor :name, :randomNumber

  validates :name, length: { in: 1..64 }
  validates :randomNumber, numericality: { only_integer: true, in: 1..10_000 }

  def random_number = Integer(randomNumber, 10)
end

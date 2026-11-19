# The JSON body of PUT /world/:id. A JSON string ("5") passes numericality,
# so the value must also be an Integer as parsed from the JSON body.
class WorldUpdate
  include ActiveModel::API

  attr_accessor :randomNumber

  validates :randomNumber, numericality: { only_integer: true, in: 1..10_000 }
  validate :json_integer

  private
    def json_integer
      errors.add(:randomNumber, "must be a JSON integer") unless randomNumber.is_a?(Integer)
    end
end

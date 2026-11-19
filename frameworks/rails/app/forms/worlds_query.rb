# The query string of GET /worlds as an Active Model object: the raw strings
# are validated (numericality only_integer reads the string itself, so "abc"
# or "1.5" fail) and converted only once they are valid.
class WorldsQuery
  include ActiveModel::API

  attr_accessor :min, :max, :limit, :page

  validates :min, :max, numericality: { only_integer: true, in: 1..10_000 }
  validates :limit, numericality: { only_integer: true, in: 1..100 }
  validates :page, numericality: { only_integer: true, in: 1..1000 }
  validate :min_not_above_max

  def initialize(attributes = {})
    super(min: "1", max: "10000", limit: "20", page: "1")
    assign_attributes(attributes)
  end

  def min_id = Integer(min, 10)
  def max_id = Integer(max, 10)
  def page_size = Integer(limit, 10)
  def offset = (Integer(page, 10) - 1) * page_size

  private
    def min_not_above_max
      return if errors.any?

      errors.add(:min, "must not be greater than max") if min_id > max_id
    end
end

Rails.application.routes.draw do
  # Define your application routes per the DSL in https://guides.rubyonrails.org/routing.html

  # Reveal health status on /up that returns 200 if the app boots with no exceptions, otherwise 500.
  # Can be used by load balancers and uptime monitors to verify that the app is live.
  get "up" => "rails/health#show", as: :rails_health_check

  # The four benchmark endpoints.
  get "text" => "bench#hello_text"
  get "json" => "bench#hello_json"
  get "db-single" => "bench#db_single"
  get "html" => "bench#hello_html"
end

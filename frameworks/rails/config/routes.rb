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

  # Phase 1: the TechEmpower-style database endpoints.
  get "queries" => "bench#queries"
  get "updates" => "bench#updates"
  get "fortunes" => "bench#fortunes"

  # Phase 2. A non-integer id matches no route (404).
  constraints id: /\d+/ do
    get "world/:id" => "worlds#show"
    put "world/:id" => "worlds#update"
  end
  get "worlds" => "worlds#index"
  get "form" => "forms#new"
  post "form" => "forms#create"
  # As `bin/rails generate authentication` routes `resource :session`, at the
  # benchmark's paths.
  get "login" => "sessions#new", as: :new_session
  post "login" => "sessions#create", as: :session
  get "me" => "users#me", as: :me
end

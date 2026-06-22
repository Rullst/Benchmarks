FROM public.ecr.aws/docker/library/elixir:1.17-alpine

RUN apk add --no-cache build-base git

WORKDIR /app

RUN mix local.hex --force && mix local.rebar --force

ENV MIX_ENV=prod

COPY mix.exs ./
RUN mix deps.get --only prod && mix deps.compile

COPY . .

RUN mix compile
RUN mix release

CMD ["_build/prod/rel/phoenix_app/bin/phoenix_app", "start"]

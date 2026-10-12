set -e

if [ ! -f .env ]; then
  echo "Crie o .env a partir do .env.example antes do primeiro deploy." >&2
  exit 1
fi

git pull
docker compose --profile prod up -d --build
docker compose ps

#!/bin/bash
# TechnoPrint Deploy Script
# Usage: cp deploy.env.example deploy.env && отредактировать && ./deploy.sh
# Настройки берутся из deploy.env (не в репозитории)

set -e

# Реальные значения (сервер, домен, токен бота) лежат в deploy.env рядом со скриптом.
# Он в .gitignore — в репозиторий не попадает. Шаблон: deploy.env.example
[ -f "$(dirname "$0")/deploy.env" ] && . "$(dirname "$0")/deploy.env"

SERVER="${TP_SERVER:?укажите TP_SERVER в deploy.env, например root@203.0.113.10}"
REMOTE_DIR="${TP_REMOTE_DIR:-/opt/technoprint}"
DOMAIN="${TP_DOMAIN:?укажите TP_DOMAIN в deploy.env, например crm.example.com}"
DB_PASSWORD="${TP_DB_PASSWORD:?укажите TP_DB_PASSWORD в deploy.env}"
TG_BOT_TOKEN="${TP_TG_BOT_TOKEN:-}"
ADMIN_EMAIL="${TP_ADMIN_EMAIL:-admin@example.com}"

echo "══════════════════════════════════"
echo "  TechnoPrint Deploy"
echo "══════════════════════════════════"

# 1. Sync files to server
echo ""
echo "[1/6] Syncing files to server..."
ssh $SERVER "mkdir -p $REMOTE_DIR/{backend,frontend}"

# Sync backend
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    backend/ $SERVER:$REMOTE_DIR/backend/

# Sync frontend
rsync -avz --delete \
    frontend/ $SERVER:$REMOTE_DIR/frontend/

# Sync docker-compose and nginx
scp docker-compose.yml $SERVER:$REMOTE_DIR/
scp nginx.conf $SERVER:/etc/nginx/sites-available/$DOMAIN

# 2. Create .env if not exists
echo ""
echo "[2/6] Setting up environment..."
ssh $SERVER "
    # пароль БД для docker compose (подстановка \${POSTGRES_PASSWORD} в docker-compose.yml)
    if [ ! -f $REMOTE_DIR/.env ]; then
        echo 'POSTGRES_PASSWORD=$DB_PASSWORD' > $REMOTE_DIR/.env
        chmod 600 $REMOTE_DIR/.env
        echo '  .env для compose создан'
    fi
    if [ ! -f $REMOTE_DIR/backend/.env ]; then
        cat > $REMOTE_DIR/backend/.env << ENVEOF
DATABASE_URL=postgresql+asyncpg://technoprint:$DB_PASSWORD@tp-db:5432/technoprint
SECRET_KEY=\$(openssl rand -hex 32)
BANK_COMMISSION=0.01
CARD_COMMISSION=0.013
TG_BOT_TOKEN=$TG_BOT_TOKEN
TG_ADMIN_CHAT_ID=
ENVEOF
        chmod 600 $REMOTE_DIR/backend/.env
        echo '  backend/.env created (set TG_ADMIN_CHAT_ID manually!)'
    else
        echo '  backend/.env already exists, skipping'
    fi
"

# 3. Build and start containers
echo ""
echo "[3/6] Building and starting containers..."
ssh $SERVER "
    cd $REMOTE_DIR
    docker compose down 2>/dev/null || true
    docker compose build --no-cache
    docker compose up -d
    echo 'Waiting for database...'
    sleep 5
    docker compose ps
"

# 4. Setup Nginx
echo ""
echo "[4/6] Configuring Nginx..."
ssh $SERVER "
    ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
    nginx -t && systemctl reload nginx
    echo '  Nginx configured for $DOMAIN'
"

# 5. SSL Certificate
echo ""
echo "[5/6] Setting up SSL..."
ssh $SERVER "
    if ! certbot certificates 2>/dev/null | grep -q '$DOMAIN'; then
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email "$ADMIN_EMAIL" || echo '  SSL setup may need manual intervention'
    else
        echo '  SSL certificate already exists'
    fi
"

# Шага «импорт данных» здесь больше нет: разовый перенос из старой системы делается
# отдельными скриптами вручную. Прогонять импорт при каждом деплое опасно — можно
# продублировать боевые данные.

echo ""
echo "══════════════════════════════════"
echo "  Deploy complete!"
echo "  URL: https://$DOMAIN"
echo "══════════════════════════════════"
echo ""
echo "  Don't forget:"
echo "    1. Set TG_ADMIN_CHAT_ID in $REMOTE_DIR/backend/.env"
echo "    2. DNS: $DOMAIN -> адрес сервера"
echo "    3. Test: https://$DOMAIN/health"

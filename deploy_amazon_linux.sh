#!/bin/bash
# Script de déploiement automatisé pour AWS EC2 Amazon Linux
# Usage: bash deploy_amazon_linux.sh

set -e  # Arrêter en cas d'erreur

echo "🚀 Démarrage du déploiement du Learning Streak Bot sur Amazon Linux..."

# Couleurs pour l'affichage
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les étapes
step() {
    echo -e "\n${GREEN}▶ $1${NC}\n"
}

error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Vérifier qu'on est sur Amazon Linux
if [ ! -f /etc/system-release ]; then
    error "Ce script est conçu pour Amazon Linux."
fi

# Afficher les informations système
info "Informations système :"
cat /etc/system-release
echo "  Kernel: $(uname -r)"
echo "  Architecture: $(uname -m)"
echo ""

# 1. Mise à jour du système
step "1/10 Mise à jour du système"
sudo yum update -y
success "Système mis à jour"

# 2. Installation de Python et dépendances
step "2/10 Installation de Python et des outils"
sudo yum install -y python3 python3-pip git gcc python3-devel
success "Python et outils installés"

# 3. Installation de PostgreSQL
step "3/10 Installation de PostgreSQL"
if ! command -v psql &> /dev/null; then
    # Installer PostgreSQL 15 depuis le repository Amazon Linux Extras
    sudo yum install -y postgresql15 postgresql15-server postgresql15-contrib postgresql15-devel
    
    # Initialiser la base de données
    sudo postgresql-setup --initdb
    
    success "PostgreSQL installé"
else
    success "PostgreSQL déjà installé"
fi

# Configurer PostgreSQL pour accepter les connexions locales avec mot de passe
sudo cp /var/lib/pgsql/data/pg_hba.conf /var/lib/pgsql/data/pg_hba.conf.backup
sudo sed -i 's/peer/md5/g' /var/lib/pgsql/data/pg_hba.conf
sudo sed -i 's/ident/md5/g' /var/lib/pgsql/data/pg_hba.conf

# Démarrer PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
success "PostgreSQL démarré et activé"

# 4. Configuration de la base de données
step "4/10 Configuration de la base de données"
echo -e "${YELLOW}Veuillez entrer un mot de passe sécurisé pour l'utilisateur PostgreSQL 'botuser' :${NC}"
read -s DB_PASSWORD
echo ""
echo -e "${YELLOW}Confirmez le mot de passe :${NC}"
read -s DB_PASSWORD_CONFIRM
echo ""

if [ "$DB_PASSWORD" != "$DB_PASSWORD_CONFIRM" ]; then
    error "Les mots de passe ne correspondent pas!"
fi

# Créer la base de données et l'utilisateur
sudo -u postgres psql << EOF
-- Créer la base de données si elle n'existe pas
SELECT 'CREATE DATABASE learning_streak' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'learning_streak')\gexec

-- Créer l'utilisateur si il n'existe pas
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'botuser') THEN
        CREATE USER botuser WITH PASSWORD '$DB_PASSWORD';
    ELSE
        ALTER USER botuser WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Donner les privilèges
GRANT ALL PRIVILEGES ON DATABASE learning_streak TO botuser;
\q
EOF

success "Base de données configurée"

# 5. Cloner ou configurer le projet
step "5/10 Configuration du projet"
PROJECT_DIR="$HOME/learning-streak-builder"

if [ -d "$PROJECT_DIR" ]; then
    echo "Le projet existe déjà à : $PROJECT_DIR"
    echo -e "${YELLOW}Voulez-vous le mettre à jour ? (y/n)${NC}"
    read UPDATE_CHOICE
    if [ "$UPDATE_CHOICE" = "y" ]; then
        cd "$PROJECT_DIR"
        if [ -d ".git" ]; then
            git pull || info "Mise à jour échouée, on continue..."
        else
            info "Pas un repository git, on continue..."
        fi
    fi
else
    echo -e "${YELLOW}URL du repository GitHub :${NC}"
    read REPO_URL
    if [ -n "$REPO_URL" ]; then
        echo -e "${YELLOW}Nom de la branche (appuyez sur Entrée pour 'main' par défaut) :${NC}"
        read BRANCH_NAME
        BRANCH_NAME=${BRANCH_NAME:-main}
        
        git clone -b "$BRANCH_NAME" "$REPO_URL" "$PROJECT_DIR"
        success "Repository cloné (branche: $BRANCH_NAME)"
    else
        mkdir -p "$PROJECT_DIR"
        echo -e "${YELLOW}⚠️  Dossier créé à : $PROJECT_DIR${NC}"
        echo "Veuillez copier vos fichiers dans ce dossier, puis relancez ce script."
        exit 0
    fi
fi

cd "$PROJECT_DIR"
success "Projet configuré dans $PROJECT_DIR"

# 6. Créer l'environnement virtuel et installer les dépendances
step "6/10 Installation des dépendances Python"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    success "Environnement virtuel créé"
else
    info "Environnement virtuel existe déjà"
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
success "Dépendances Python installées"

# 7. Configuration du fichier .env
step "7/10 Configuration des variables d'environnement"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Token Discord Bot :${NC}"
    read DISCORD_TOKEN
    
    echo -e "${YELLOW}Clé API Groq :${NC}"
    read GROQ_KEY
    
    cat > .env << EOF
DISCORD_BOT_TOKEN=$DISCORD_TOKEN
DATABASE_URL=postgresql://botuser:$DB_PASSWORD@localhost:5432/learning_streak
GROQ_API_KEY=$GROQ_KEY
EOF
    success "Fichier .env créé"
else
    info "Fichier .env existe déjà"
    echo -e "${YELLOW}Voulez-vous le reconfigurer ? (y/n)${NC}"
    read RECONFIG_ENV
    if [ "$RECONFIG_ENV" = "y" ]; then
        echo -e "${YELLOW}Token Discord Bot :${NC}"
        read DISCORD_TOKEN
        
        echo -e "${YELLOW}Clé API Groq :${NC}"
        read GROQ_KEY
        
        cat > .env << EOF
DISCORD_BOT_TOKEN=$DISCORD_TOKEN
DATABASE_URL=postgresql://botuser:$DB_PASSWORD@localhost:5432/learning_streak
GROQ_API_KEY=$GROQ_KEY
EOF
        success "Fichier .env reconfiguré"
    fi
fi

# 8. Test de connexion à la base de données
step "8/10 Test de connexion à la base de données"
export PGPASSWORD=$DB_PASSWORD
if psql -U botuser -d learning_streak -h localhost -c "SELECT 1;" > /dev/null 2>&1; then
    success "Connexion à la base de données réussie"
else
    error "Échec de connexion à la base de données"
fi
unset PGPASSWORD

# 9. Test du bot (rapide)
step "9/10 Test initial du bot"
echo "Test du bot pendant 5 secondes..."
timeout 5 python3 bot.py || true
success "Test du bot effectué"

# 10. Configuration du service systemd
step "10/10 Configuration du service système"
SERVICE_FILE="/etc/systemd/system/learning-streak-bot.service"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Learning Streak Builder Discord Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Sécurité
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd et activer le service
sudo systemctl daemon-reload
sudo systemctl enable learning-streak-bot

# Arrêter le service si il tourne déjà
sudo systemctl stop learning-streak-bot 2>/dev/null || true

# Démarrer le service
sudo systemctl start learning-streak-bot

# Attendre un peu que le service démarre
sleep 3

success "Service configuré et démarré"

# Afficher le statut
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
success "🎉 Déploiement terminé avec succès sur Amazon Linux !"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Statut du bot :"
echo ""
sudo systemctl status learning-streak-bot --no-pager || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Commandes utiles :"
echo ""
echo "  • Voir les logs en temps réel :"
echo "    ${GREEN}sudo journalctl -u learning-streak-bot -f${NC}"
echo ""
echo "  • Redémarrer le bot :"
echo "    ${GREEN}sudo systemctl restart learning-streak-bot${NC}"
echo ""
echo "  • Arrêter le bot :"
echo "    ${GREEN}sudo systemctl stop learning-streak-bot${NC}"
echo ""
echo "  • Voir le statut :"
echo "    ${GREEN}sudo systemctl status learning-streak-bot${NC}"
echo ""
echo "  • Mettre à jour le bot :"
echo "    ${GREEN}cd $PROJECT_DIR && git pull && sudo systemctl restart learning-streak-bot${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
info "💡 Instance EC2 détectée :"
INSTANCE_ID=$(ec2-metadata --instance-id 2>/dev/null | cut -d " " -f 2 || echo "N/A")
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
REGION=$(ec2-metadata --availability-zone 2>/dev/null | cut -d " " -f 2 | sed 's/.$//' || echo "N/A")

echo "  Instance ID  : $INSTANCE_ID"
echo "  IP Publique  : $PUBLIC_IP"
echo "  Région       : $REGION"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✨ Votre bot Discord est maintenant opérationnel 24/7 sur Amazon Linux !"
echo ""
echo "🔍 Testez sur Discord : ${GREEN}!start${NC} ${GREEN}!challenge${NC} ${GREEN}!streak${NC}"
echo ""
